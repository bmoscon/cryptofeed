'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
import time
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, CANDLES, GATEIO, L2_BOOK, TICKER, TRADES, BUY, SELL
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Candle


LOG = logging.getLogger('feedhandler')


class Gateio(Feed):
    id = GATEIO
    symbol_endpoint = "https://api.gateio.ws/api/v4/spot/currency_pairs"
    valid_candle_intervals = {'10s', '1m', '5m', '15m', '30m', '1h', '4h', '8h', '1d', '3d'}
    websocket_channels = {
        L2_BOOK: 'spot.order_book_update',
        TRADES: 'spot.trades',
        TICKER: 'spot.tickers',
        CANDLES: 'spot.candlesticks'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for entry in data:
            if entry["trade_status"] != "tradable":
                continue
            s = Symbol(entry['base'], entry['quote'])
            ret[s.normalized] = entry['id']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://api.gateio.ws/ws/v4/', **kwargs)
        self.ws_defaults['compression'] = None
        self._reset()

    def _reset(self):
        self._l2_book = {}
        self.last_update_id = {}
        self.forced = defaultdict(bool)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'time': 1618876417,
            'channel': 'spot.tickers',
            'event': 'update',
            'result': {
                'currency_pair': 'BTC_USDT',
                'last': '55636.45',
                'lowest_ask': '55634.06',
                'highest_bid': '55634.05',
                'change_percentage': '-0.7634',
                'base_volume': '1138.9062880772',
                'quote_volume': '63844439.342660318028',
                'high_24h': '63736.81',
                'low_24h': '50986.18'
            }
        }
        """
        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['result']['currency_pair']),
            Decimal(msg['result']['highest_bid']),
            Decimal(msg['result']['lowest_ask']),
            float(msg['time']),
            raw=msg
        )
        await self.callback(TICKER, t, timestamp)

    async def _trades(self, msg: dict, timestamp: float):
        """
        {
            "time": 1606292218,
            "channel": "spot.trades",
            "event": "update",
            "result": {
                "id": 309143071,
                "create_time": 1606292218,
                "create_time_ms": "1606292218213.4578",
                "side": "sell",
                "currency_pair": "GT_USDT",
                "amount": "16.4700000000",
                "price": "0.4705000000"
            }
        }
        """
        t = Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['result']['currency_pair']),
            SELL if msg['result']['side'] == 'sell' else BUY,
            Decimal(msg['result']['amount']),
            Decimal(msg['result']['price']),
            float(msg['result']['create_time_ms']) / 1000,
            id=str(msg['result']['id']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _snapshot(self, symbol: str):
        """
        {
            "id": 2679059670,
            "asks": [[price, amount], [...], ...],
            "bids": [[price, amount], [...], ...]
        }
        """
        url = f'https://api.gateio.ws/api/v4/spot/order_book?currency_pair={symbol}&limit=100&with_id=true'
        ret = await self.http_conn.read(url)
        data = json.loads(ret, parse_float=Decimal)

        symbol = self.exchange_symbol_to_std_symbol(symbol)
        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        self.last_update_id[symbol] = data['id']
        self._l2_book[symbol].book.bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
        self._l2_book[symbol].book.asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
        await self.book_callback(L2_BOOK, self._l2_book[symbol], time.time(), raw=data, sequence_number=data['id'])

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool]:
        skip_update = False
        forced = not self.forced[pair]

        if forced and msg['u'] <= self.last_update_id[pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[pair] + 1 <= msg['u']:
            self.last_update_id[pair] = msg['u']
            self.forced[pair] = True
        elif not forced and self.last_update_id[pair] + 1 == msg['U']:
            self.last_update_id[pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True

        return skip_update

    async def _process_l2_book(self, msg: dict, timestamp: float):
        """
        {
            'time': 1618961347,
            'channel': 'spot.order_book_update',
            'event': 'update',
            'result': {
                't': 1618961347345,   ms timestamp
                'e': 'depthUpdate',   ignore
                'E': 1618961347,      deprecated timestamp
                's': 'BTC_USDT',      symbol
                'U': 2679731734,      start of update seq no
                'u': 2679731743,      end of update seq no
                'b': [['56444.4', '0.01'], ['56080.11', '0']],
                'a': [['56447.57', '0.1252'], ['56448.44', '0'], ['56467.28', '0'], ['56470.74', '0']]
            }
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['result']['s'])
        if symbol not in self._l2_book:
            await self._snapshot(msg['result']['s'])

        skip_update = self._check_update_id(symbol, msg['result'])
        if skip_update:
            return

        ts = msg['result']['t'] / 1000
        delta = {BID: [], ASK: []}

        for s, side in (('b', BID), ('a', ASK)):
            for update in msg['result'][s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self._l2_book[symbol].book[side]:
                        del self._l2_book[symbol].book[side][price]
                        delta[side].append((price, amount))
                else:
                    self._l2_book[symbol].book[side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, timestamp=ts, raw=msg)

    async def _candles(self, msg: dict, timestamp: float):
        """
        {
            'time': 1619092863,
            'channel': 'spot.candlesticks',
            'event': 'update',
            'result': {
                't': '1619092860',
                'v': '1154.64627',
                'c': '54992.64',
                'h': '54992.64',
                'l': '54976.29',
                'o': '54976.29',
                'n': '1m_BTC_USDT'
            }
        }
        """
        interval, symbol = msg['result']['n'].split('_', 1)
        if interval == '7d':
            interval = '1w'
        c = Candle(
            self.id,
            self.exchange_symbol_to_std_symbol(symbol),
            float(msg['result']['t']),
            float(msg['result']['t']) + 59,
            interval,
            None,
            Decimal(msg['result']['o']),
            Decimal(msg['result']['c']),
            Decimal(msg['result']['h']),
            Decimal(msg['result']['l']),
            Decimal(msg['result']['v']),
            None,
            float(msg['time']),
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if "error" in msg:
            if msg['error'] is None:
                pass
            else:
                LOG.warning("%s: Error received from exchange - %s", self.id, msg)
        if msg['event'] == 'subscribe':
            return
        elif 'channel' in msg:
            market, channel = msg['channel'].split('.')
            if channel == 'tickers':
                await self._ticker(msg, timestamp)
            elif channel == 'trades':
                await self._trades(msg, timestamp)
            elif channel == 'order_book_update':
                await self._process_l2_book(msg, timestamp)
            elif channel == 'candlesticks':
                await self._candles(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self._reset()
        for chan in self.subscription:
            symbols = self.subscription[chan]
            nchan = self.exchange_channel_to_std(chan)
            if nchan in {L2_BOOK, CANDLES}:
                for symbol in symbols:
                    await conn.write(json.dumps(
                        {
                            "time": int(time.time()),
                            "channel": chan,
                            "event": 'subscribe',
                            "payload": [symbol, '100ms'] if nchan == L2_BOOK else [self.candle_interval, symbol],
                        }
                    ))
            else:
                await conn.write(json.dumps(
                    {
                        "time": int(time.time()),
                        "channel": chan,
                        "event": 'subscribe',
                        "payload": symbols,
                    }
                ))
