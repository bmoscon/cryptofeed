'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import time
from typing import Dict, Tuple
import hmac
import base64
import hashlib

from yapic import json

from cryptofeed.defines import ASK, BID, BUY, CANDLES, KUCOIN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.symbols import Symbol
from cryptofeed.connection import AsyncConnection
from cryptofeed.types import OrderBook, Trade, Ticker, Candle


LOG = logging.getLogger('feedhandler')


class KuCoin(Feed):
    id = KUCOIN
    symbol_endpoint = 'https://api.kucoin.com/api/v1/symbols'
    valid_candle_intervals = {'1m', '3m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w'}
    websocket_channels = {
        L2_BOOK: '/market/level2',
        TRADES: '/market/match',
        TICKER: '/market/ticker',
        CANDLES: '/market/candles'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'tick_size': {}, 'instrument_type': {}}
        for symbol in data['data']:
            if not symbol['enableTrading']:
                continue
            s = Symbol(symbol['baseCurrency'], symbol['quoteCurrency'])
            info['tick_size'][s.normalized] = symbol['priceIncrement']
            ret[s.normalized] = symbol['symbol']
            info['instrument_type'][s.normalized] = s.type
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
        self._l2_book = {}
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
        c = Candle(
            self.id,
            symbol,
            int(start),
            end,
            interval,
            None,
            Decimal(open),
            Decimal(close),
            Decimal(high),
            Decimal(low),
            Decimal(vol),
            None,
            msg['data']['time'] / 1000000000,
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

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
        t = Ticker(self.id, symbol, Decimal(msg['data']['bestBid']), Decimal(msg['data']['bestAsk']), None, raw=msg)
        await self.callback(TICKER, t, timestamp)

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
        t = Trade(
            self.id,
            symbol,
            BUY if msg['data']['side'] == 'buy' else SELL,
            Decimal(msg['data']['size']),
            Decimal(msg['data']['price']),
            float(msg['data']['time']) / 1000000000,
            id=msg['data']['tradeId'],
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    def generate_token(self, str_to_sign: str) -> dict:
        # https://docs.kucoin.com/#authentication

        # Now required to pass timestamp with string to sign. Timestamp should exactly match header timestamp
        now = str(int(time.time() * 1000))
        str_to_sign = now + str_to_sign
        signature = base64.b64encode(hmac.new(self.key_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
        # Passphrase must now be encrypted by key_secret
        passphrase = base64.b64encode(hmac.new(self.key_secret.encode('utf-8'), self.key_passphrase.encode('utf-8'), hashlib.sha256).digest())

        # API key version is currently 2 (whereas API version is anywhere from 1-3 ¯\_(ツ)_/¯)
        header = {
            "KC-API-KEY": self.key_id,
            "KC-API-SIGN": signature.decode(),
            "KC-API-TIMESTAMP": now,
            "KC-API-PASSPHRASE": passphrase.decode(),
            "KC-API-KEY-VERSION": "2"
        }
        return header

    async def _snapshot(self, symbol: str):
        url = f"https://api.kucoin.com/api/v3/market/orderbook/level2?symbol={symbol}"
        str_to_sign = "GET" + f"/api/v3/market/orderbook/level2?symbol={symbol}"
        headers = self.generate_token(str_to_sign)
        data = await self.http_conn.read(url, header=headers)
        timestamp = time.time()
        data = json.loads(data, parse_float=Decimal)
        data = data['data']
        self.seq_no[symbol] = int(data['sequence'])
        bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
        asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks)

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, raw=data, sequence_number=int(data['sequence']))

    async def _process_l2_book(self, msg: dict, symbol: str, timestamp: float):
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
        data = msg['data']
        sequence = data['sequenceStart']
        if symbol not in self._l2_book or sequence > self.seq_no[symbol] + 1:
            if symbol in self.seq_no and sequence > self.seq_no[symbol] + 1:
                LOG.warning("%s: Missing book update detected, resetting book", self.id)
            await self._snapshot(symbol)

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
                    if price in self._l2_book[symbol].book[side]:
                        del self._l2_book[symbol].book[side][price]
                        delta[side].append((price, amount))
                else:
                    self._l2_book[symbol].book[side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, raw=msg, sequence_number=data['sequenceEnd'])

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if msg['type'] in {'welcome', 'ack'}:
            return

        topic, symbol = msg['topic'].split(":", 1)
        topic = self.exchange_channel_to_std(topic)

        if topic == TICKER:
            await self._ticker(msg, symbol, timestamp)
        elif topic == TRADES:
            await self._trades(msg, symbol, timestamp)
        elif topic == CANDLES:
            await self._candles(msg, symbol, timestamp)
        elif topic == L2_BOOK:
            await self._process_l2_book(msg, symbol, timestamp)
        else:
            LOG.warning("%s: Unhandled message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            symbols = self.subscription[chan]
            nchan = self.exchange_channel_to_std(chan)
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
