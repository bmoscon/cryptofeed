'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
import logging
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BUY, CANDLES, FMFW as FMFW_id, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Candle
from cryptofeed.util.time import timedelta_str_to_sec


LOG = logging.getLogger('feedhandler')


class FMFW(Feed):
    id = FMFW_id
    websocket_endpoints = [WebsocketEndpoint('wss://api.fmfw.io/api/3/ws/public')]
    rest_endpoints = [RestEndpoint('https://api.fmfw.io', routes=Routes('/api/3/public/symbol'))]

    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'}
    candle_interval_map = {'1m': 'M1', '3m': 'M3', '5m': 'M5', '15m': 'M15', '30m': 'M30', '1h': 'H1', '4h': 'H4', '1d': 'D1', '1w': 'D7', '1M': '1M'}
    websocket_channels = {
        L2_BOOK: 'orderbook/full',
        TRADES: 'trades',
        TICKER: 'ticker/1s',
        CANDLES: 'candles/'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for sym, symbol in data.items():
            s = Symbol(symbol['base_currency'], symbol['quote_currency'])
            ret[s.normalized] = sym
            info['tick_size'][s.normalized] = symbol['tick_size']
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    async def _book(self, msg: dict, ts: float):
        if 'snapshot' in msg:
            for pair, update in msg['snapshot'].items():
                symbol = self.exchange_symbol_to_std_symbol(pair)
                bids = {Decimal(price): Decimal(size) for price, size in update['b']}
                asks = {Decimal(price): Decimal(size) for price, size in update['a']}
                self._l2_book[symbol] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
                await self.book_callback(L2_BOOK, self._l2_book[symbol], ts, sequence_number=update['s'], delta=None, raw=msg, timestamp=self.timestamp_normalize(update['t']))
                self.seq_no[symbol] = update['s']
        else:
            delta = {BID: [], ASK: []}
            for pair, update in msg['update'].items():
                symbol = self.exchange_symbol_to_std_symbol(pair)

                if self.seq_no[symbol] + 1 != update['s']:
                    raise MissingSequenceNumber
                self.seq_no[symbol] = update['s']

                for side, key in ((BID, 'b'), (ASK, 'a')):
                    for price, size in update[key]:
                        price = Decimal(price)
                        size = Decimal(size)
                        delta[side].append((price, size))
                        if size == 0:
                            del self._l2_book[symbol].book[side][price]
                        else:
                            self._l2_book[symbol].book[side][price] = size
                    await self.book_callback(L2_BOOK, self._l2_book[symbol], ts, sequence_number=update['s'], delta=delta, raw=msg, timestamp=self.timestamp_normalize(update['t']))

    async def _trade(self, msg: dict, ts: float):
        '''
        {
            'ch': 'trades',
            'update': {
                'BTCUSDT': [{
                    't': 1633803835228,
                    'i': 1633803835228,
                    'p': '54774.60',
                    'q': '0.00004',
                    's': 'buy'
                }]
            }
        }
        '''
        for pair, update in msg['update'].items():
            symbol = self.exchange_symbol_to_std_symbol(pair)
            for trade in update:
                t = Trade(
                    self.id,
                    symbol,
                    BUY if trade['s'] == 'buy' else SELL,
                    Decimal(trade['q']),
                    Decimal(trade['p']),
                    self.timestamp_normalize(trade['t']),
                    id=str(trade['i']),
                    raw=msg
                )
                await self.callback(TRADES, t, ts)

    async def _ticker(self, msg: dict, ts: float):
        '''
        {
            'ch': 'ticker/1s',
            'data': {
                'BTCUSDT': {
                    't': 1633804289795,
                    'a': '54813.56',
                    'A': '0.82000',
                    'b': '54810.31',
                    'B': '0.00660',
                    'o': '54517.48',
                    'c': '54829.88',
                    'h': '55493.92',
                    'l': '53685.61',
                    'v': '19025.22558',
                    'q': '1040244549.4048389',
                    'p': '312.40',
                    'P': '0.5730272198935094',
                    'L': 1417964345
                }
            }
        }
        '''
        for sym, ticker in msg['data'].items():
            t = Ticker(
                self.id,
                self.exchange_symbol_to_std_symbol(sym),
                Decimal(ticker['b']),
                Decimal(ticker['a']),
                self.timestamp_normalize(ticker['t']),
                raw=msg
            )
            await self.callback(TICKER, t, ts)

    async def _candle(self, msg: dict, ts: float):
        '''
        {
            'ch': 'candles/M1',
            'update': {
                'BTCUSDT': [{
                    't': 1633805940000,
                    'o': '54849.03',
                    'c': '54849.03',
                    'h': '54849.03',
                    'l': '54849.03',
                    'v': '0.00766',
                    'q': '420.1435698'
                }]
            }
        }
        '''
        interval = msg['ch'].split("/")[-1]
        for sym, updates in msg['update'].items():
            symbol = self.exchange_symbol_to_std_symbol(sym)
            for u in updates:
                c = Candle(
                    self.id,
                    symbol,
                    u['t'] / 1000,
                    u['t'] / 1000 + timedelta_str_to_sec(self.normalize_candle_interval[interval]) - 0.1,
                    self.normalize_candle_interval[interval],
                    None,
                    Decimal(u['o']),
                    Decimal(u['c']),
                    Decimal(u['h']),
                    Decimal(u['l']),
                    Decimal(u['v']),
                    None,
                    self.timestamp_normalize(u['t']),
                    raw=msg)
                await self.callback(CANDLES, c, ts)

    async def message_handler(self, msg: str, conn, ts: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'result' in msg:
            LOG.debug("%s: Info message from exchange: %s", conn.uuid, msg)
        elif msg['ch'] == 'orderbook/full':
            await self._book(msg, ts)
        elif msg['ch'] == 'trades':
            await self._trade(msg, ts)
        elif msg['ch'] == 'ticker/1s':
            await self._ticker(msg, ts)
        elif msg['ch'].startswith('candles/'):
            await self._candle(msg, ts)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn):
        self.__reset()

        for chan in self.subscription:
            await conn.write(json.dumps({"method": "subscribe",
                                         "params": {"symbols": self.subscription[chan]},
                                         "ch": chan if chan != 'candles/' else chan + self.candle_interval_map[self.candle_interval],
                                         "id": 1234
                                         }))
