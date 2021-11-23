'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json
from cryptofeed.connection import AsyncConnection

from cryptofeed.defines import BUY, CANDLES, CRYPTODOTCOM, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Trade, Ticker, Candle, OrderBook


LOG = logging.getLogger('feedhandler')


class CryptoDotCom(Feed):
    id = CRYPTODOTCOM
    symbol_endpoint = 'https://api.crypto.com/v2/public/get-instruments'
    websocket_channels = {
        L2_BOOK: 'book',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candlestick'
    }
    request_limit = 100
    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '6h', '12h', '1d', '1w', '2w', '1M'}

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['result']['instruments']:
            sym = Symbol(entry['base_currency'], entry['quote_currency'])
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['instrument_name']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://stream.crypto.com/v2/market', **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _trades(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'trade.BTC_USDT',
            'channel': 'trade',
            'data': [
                {
                    'dataTime': 1637630445449,
                    'd': 2006341810221954784,
                    's': 'BUY',
                    'p': Decimal('56504.25'),
                    'q': Decimal('0.003802'),
                    't': 1637630445448,
                    'i': 'BTC_USDT'
                }
            ]
        }
        '''
        for entry in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['instrument_name']),
                BUY if entry['s'] == 'BUY' else SELL,
                entry['q'],
                entry['p'],
                self.timestamp_normalize(entry['t']),
                id=str(entry['d']),
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'ticker.BTC_USDT',
            'channel': 'ticker',
            'data': [
                {
                    'i': 'BTC_USDT',
                    'b': Decimal('57689.90'),
                    'k': Decimal('57690.90'),
                    'a': Decimal('57690.90'),
                    't': 1637705099140,
                    'v': Decimal('46427.152283'),
                    'h': Decimal('57985.00'),
                    'l': Decimal('55313.95'),
                    'c': Decimal('1311.15')
                }
            ]
        }
        '''
        for entry in msg['data']:
            await self.callback(TICKER, Ticker(self.id, self.exchange_symbol_to_std_symbol(entry['i']), entry['b'], entry['a'], self.timestamp_normalize(entry['t']), raw=entry), timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'candlestick.14D.BTC_USDT',
            'channel': 'candlestick',
            'depth': 300,
            'interval': '14D',
            'data': [
                {
                    't': 1636934400000,
                    'o': Decimal('65502.68'),
                    'h': Decimal('66336.25'),
                    'l': Decimal('55313.95'),
                    'c': Decimal('57582.1'),
                    'v': Decimal('366802.492134')
                }
            ]
        }
        '''
        interval = msg['interval']
        if interval == '14D':
            interval = '2w'
        elif interval == '7D':
            interval = '1w'
        elif interval == '1D':
            interval = '1d'

        for entry in msg['data']:
            c = Candle(self.id,
                       self.exchange_symbol_to_std_symbol(msg['instrument_name']),
                       entry['t'] / 1000,
                       entry['t'] / 1000 + timedelta_str_to_sec(interval) - 1,
                       interval,
                       None,
                       entry['o'],
                       entry['c'],
                       entry['h'],
                       entry['l'],
                       entry['v'],
                       None,
                       None,
                       raw=entry)
            await self.callback(CANDLES, c, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'book.BTC_USDT.150',
            'channel': 'book',
            'depth': 150,
            'data': [
                {
                    'bids': [
                        [Decimal('57553.03'), Decimal('0.481606'), 2],
                        [Decimal('57552.47'), Decimal('0.000418'), 1],
                        ...
                    ]
                    'asks': [
                        [Decimal('57555.44'), Decimal('0.343236'), 1],
                        [Decimal('57555.95'), Decimal('0.026062'), 1],
                        ...
                    ]
                }
            ]
        }
        '''
        pair = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            if pair not in self._l2_book:
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

            self._l2_book[pair].book.bids = {price: amount for price, amount, _ in entry['bids']}
            self._l2_book[pair].book.asks = {price: amount for price, amount, _ in entry['asks']}

            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(entry['t']), raw=entry)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['method'] == 'public/heartbeat':
            msg['method'] = 'public/respond-heartbeat'
            await conn.write(json.dumps(msg))
            return

        if msg['code'] != 0:
            LOG.warning("%s: Error received from exchange %s", self.id, msg)
            return

        channel = msg.get('result', {}).get('channel')
        if channel == 'trade':
            await self._trades(msg['result'], timestamp)
        elif channel == 'ticker':
            await self._ticker(msg['result'], timestamp)
        elif channel == 'candlestick':
            await self._candle(msg['result'], timestamp)
        elif channel == 'book':
            await self._book(msg['result'], timestamp)
        elif channel is None:
            return
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        # API Docs recommend a sleep between connect and subscription to avoid rate limiting
        await asyncio.sleep(1)
        for chan, symbols in self.subscription.items():
            def sym(chan, symbol):
                chan_s = self.exchange_channel_to_std(chan)
                if chan_s == L2_BOOK:
                    return f"{chan}.{symbol}.150"
                if chan_s == CANDLES:
                    interval = self.candle_interval
                    if self.candle_interval == '1d':
                        interval = '1D'
                    elif self.candle_interval == '1w':
                        interval = '7D'
                    elif self.candle_interval == '2w':
                        interval = '14D'
                    return f"{chan}.{interval}.{symbol}"
                return f"{chan}.{symbol}"

            await conn.write(json.dumps({"method": "subscribe",
                                        "params": {
                                            "channels": [sym(chan, symbol) for symbol in symbols]
                                        }}))
            await asyncio.sleep(1)
