'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.standards import normalize_channel
from cryptofeed.connection import AsyncConnection
from decimal import Decimal
import logging
import time
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import ASK, BID, BUY, CANDLES, KUCOIN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.util.time import timedelta_str_to_sec

LOG = logging.getLogger('feedhandler')


class KuCoin(Feed):
    id = KUCOIN
    symbol_endpoint = 'https://api.kucoin.com/api/v1/symbols'
    valid_candle_intervals = {'1m', '3m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w'}

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'tick_size': {}}
        for symbol in data['data']:
            if not symbol['enableTrading']:
                continue
            sym = symbol['symbol']
            info['tick_size'][sym] = symbol['priceIncrement']
            ret[sym] = sym
        return ret, info

    def __init__(self, candle_interval='1m', **kwargs):
        address_info = self.http_sync.write('https://api.kucoin.com/api/v1/bullet-public', json=True)
        token = address_info['data']['token']
        address = address_info['data']['instanceServers'][0]['endpoint']
        address = f"{address}?token={token}"
        super().__init__(address, **kwargs)
        self.ws_defaults['ping_interval'] = address_info['data']['instanceServers'][0]['pingInterval'] / 2000
        lookup = {'1m': '1min', '3m': '3min', '15m': '15min', '30m': '30min', '1h': '1hour', '2h': '2hour', '4h': '4hour', '6h': '6hour', '8h': '8hour', '12h': '12hour', '1d': '1day', '1w': '1week'}
        self.candle_interval = lookup[candle_interval]
        self.normalize_interval = {value: key for key, value in lookup.items()}
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.seq_no = {}

    async def _candles(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            'data': {
                'symbol': 'BTC-USDT',
                'candles': ['1619196960', '49885.4', '49821', '49890.5', '49821', '2.60137567', '129722.909001802'],
                'time': 1619196997007846442
            },
            'subject': 'trade.candles.update',
            'topic': '/market/candles:BTC-USDT_1min',
            'type': 'message'
        }
        """
        symbol, interval = symbol.split("_")
        interval = self.normalize_interval[interval]
        start, open, close, high, low, vol, _ = msg['data']['candles']
        end = int(start) + timedelta_str_to_sec(interval) - 1
        await self.callback(CANDLES,
                            feed=self.id,
                            symbol=symbol,
                            timestamp=msg['data']['time'] / 1000000000,
                            receipt_timestamp=timestamp,
                            start=int(start),
                            stop=end,
                            interval=interval,
                            trades=None,
                            open_price=Decimal(open),
                            close_price=Decimal(close),
                            high_price=Decimal(high),
                            low_price=Decimal(low),
                            volume=Decimal(vol),
                            closed=None)

    async def _ticker(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            "type":"message",
            "topic":"/market/ticker:BTC-USDT",
            "subject":"trade.ticker",
            "data":{

                "sequence":"1545896668986", // Sequence number
                "price":"0.08",             // Last traded price
                "size":"0.011",             //  Last traded amount
                "bestAsk":"0.08",          // Best ask price
                "bestAskSize":"0.18",      // Best ask size
                "bestBid":"0.049",         // Best bid price
                "bestBidSize":"0.036"     // Best bid size
            }
        }
        """
        await self.callback(TICKER, feed=self.id,
                            symbol=symbol,
                            bid=Decimal(msg['data']['bestBid']),
                            ask=Decimal(msg['data']['bestAsk']),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def _trades(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            "type":"message",
            "topic":"/market/match:BTC-USDT",
            "subject":"trade.l3match",
            "data":{

                "sequence":"1545896669145",
                "type":"match",
                "symbol":"BTC-USDT",
                "side":"buy",
                "price":"0.08200000000000000000",
                "size":"0.01022222000000000000",
                "tradeId":"5c24c5da03aa673885cd67aa",
                "takerOrderId":"5c24c5d903aa6772d55b371e",
                "makerOrderId":"5c2187d003aa677bd09d5c93",
                "time":"1545913818099033203"
            }
        }
        """
        await self.callback(TRADES, feed=self.id,
                            symbol=symbol,
                            side=BUY if msg['data']['side'] == 'buy' else SELL,
                            amount=Decimal(msg['data']['size']),
                            price=Decimal(msg['data']['price']),
                            timestamp=float(msg['data']['time']) / 1000000000,
                            receipt_timestamp=timestamp,
                            order_id=msg['data']['tradeId'])

    async def _snapshot(self, symbol: str):
        url = f"https://api.kucoin.com/api/v2/market/orderbook/level2?symbol={symbol}"
        data = await self.http_conn.read(url)
        data = json.loads(data, parse_float=Decimal)
        data = data['data']
        self.seq_no[symbol] = int(data['sequence'])
        self.l2_book[symbol] = {
            BID: sd({Decimal(price): Decimal(amount) for price, amount in data['bids']}),
            ASK: sd({Decimal(price): Decimal(amount) for price, amount in data['asks']})
        }

        timestamp = time.time()
        await self.book_callback(self.l2_book[symbol], L2_BOOK, symbol, True, None, timestamp, timestamp)

    async def _l2_book(self, msg: dict, symbol: str, timestamp: float):
        """
        {
            'data': {
                'sequenceStart': 1615591136351,
                'symbol': 'BTC-USDT',
                'changes': {
                    'asks': [],
                    'bids': [['49746.9', '0.1488295', '1615591136351']]
                },
                'sequenceEnd': 1615591136351
            },
            'subject': 'trade.l2update',
            'topic': '/market/level2:BTC-USDT',
            'type': 'message'
        }
        """
        forced = False
        data = msg['data']
        sequence = data['sequenceStart']
        if symbol not in self.l2_book or sequence > self.seq_no[symbol] + 1:
            if symbol in self.seq_no and sequence > self.seq_no[symbol] + 1:
                LOG.warning("%s: Missing book update detected, resetting book", self.id)
            await self._snapshot(symbol)
            forced = True

        data = msg['data']
        if sequence < self.seq_no[symbol]:
            return

        self.seq_no[symbol] = data['sequenceEnd']

        delta = {BID: [], ASK: []}
        for s, side in (('bids', BID), ('asks', ASK)):
            for update in data['changes'][s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self.l2_book[symbol][side]:
                        del self.l2_book[symbol][side][price]
                        delta[side].append((price, amount))
                else:
                    self.l2_book[symbol][side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(self.l2_book[symbol], L2_BOOK, symbol, forced, delta, timestamp, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if msg['type'] in {'welcome', 'ack'}:
            return

        topic, symbol = msg['topic'].split(":", 1)
        topic = normalize_channel(self.id, topic)

        if topic == TICKER:
            await self._ticker(msg, symbol, timestamp)
        elif topic == TRADES:
            await self._trades(msg, symbol, timestamp)
        elif topic == CANDLES:
            await self._candles(msg, symbol, timestamp)
        elif topic == L2_BOOK:
            await self._l2_book(msg, symbol, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            symbols = self.subscription[chan]
            nchan = normalize_channel(self.id, chan)
            if nchan == CANDLES:
                for symbol in symbols:
                    await conn.write(json.dumps({
                        'id': 1,
                        'type': 'subscribe',
                        'topic': f"{chan}:{symbol}_{self.candle_interval}",
                        'privateChannel': False,
                        'response': True
                    }))
            else:
                await conn.write(json.dumps({
                    'id': 1,
                    'type': 'subscribe',
                    'topic': f"{chan}:{','.join(symbols)}",
                    'privateChannel': False,
                    'response': True
                }))
