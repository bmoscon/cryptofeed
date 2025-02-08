'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint

from cryptofeed.defines import BUY, CALL, CANDLES, DELTA, FUTURES, L2_BOOK, OPTION, PERPETUAL, PUT, SELL, SPOT, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Trade, Candle, OrderBook


LOG = logging.getLogger('feedhandler')


class Delta(Feed):
    id = DELTA
    websocket_endpoints = [WebsocketEndpoint('wss://socket.delta.exchange', sandbox='wss://testnet-socket.delta.exchange')]
    rest_endpoints = [RestEndpoint('https://api.delta.exchange', routes=Routes('/v2/products'))]

    websocket_channels = {
        L2_BOOK: 'l2_orderbook',
        TRADES: 'all_trades',
        CANDLES: 'candlestick_',
    }
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '2w', '1M'}
    candle_interval_map = {'1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '12h': '12h', '1d': '1d', '1w': '1w', '2w': '2w', '1M': '30d'}

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['result']:
            quote = entry['quoting_asset']['symbol']
            base = entry['underlying_asset']['symbol']
            if entry['contract_type'] == 'spot':
                sym = Symbol(base, quote, type=SPOT)
            elif entry['contract_type'] == 'perpetual_futures':
                sym = Symbol(base, quote, type=PERPETUAL)
            elif entry['contract_type'] == 'futures' or entry['contract_type'] == 'move_options':
                sym = Symbol(base, quote, type=FUTURES, expiry_date=entry['settlement_time'])
            elif entry['contract_type'] == 'call_options' or entry['contract_type'] == 'put_options':
                otype = PUT if entry['contract_type'].startswith('put') else CALL
                sym = Symbol(base, quote, type=OPTION, strike_price=entry['strike_price'], expiry_date=entry['settlement_time'], option_type=otype)
            elif entry['contract_type'] in {'interest_rate_swaps', 'spreads', 'options_combos'}:
                continue
            else:
                raise ValueError(entry['contract_type'])

            info['instrument_type'][sym.normalized] = sym.type
            info['tick_size'][sym.normalized] = entry['tick_size']
            ret[sym.normalized] = entry['symbol']
        return ret, info

    def __reset(self):
        self._l2_book = {}

    async def _trades(self, msg: dict, timestamp: float):
        '''
        {
            'buyer_role': 'taker',
            'price': '54900.0',
            'product_id': 8320,
            'seller_role': 'maker',
            'size': '0.000695',
            'symbol': 'BTC_USDT',
            'timestamp': 1638132618257226,
            'type': 'all_trades'
        }
        '''
        if msg['type'] == 'all_trades':
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['symbol']),
                BUY if msg['buyer_role'] == 'taker' else SELL,
                Decimal(msg['size']),
                Decimal(msg['price']),
                self.timestamp_normalize(msg['timestamp']),
                raw=msg
            )
            await self.callback(TRADES, t, timestamp)
        else:
            for trade in msg['trades']:
                t = Trade(
                    self.id,
                    self.exchange_symbol_to_std_symbol(msg['symbol']),
                    BUY if trade['buyer_role'] == 'taker' else SELL,
                    Decimal(trade['size']),
                    Decimal(trade['price']),
                    self.timestamp_normalize(trade['timestamp']),
                    raw=trade
                )
                await self.callback(TRADES, t, timestamp)

    async def _candles(self, msg: dict, timestamp: float):
        '''
        {
            'candle_start_time': 1638134700000000,
            'close': None,
            'high': None,
            'last_updated': 1638134700318213,
            'low': None,
            'open': None,
            'resolution': '1m',
            'symbol': 'BTC_USDT',
            'timestamp': 1638134708903082,
            'type': 'candlestick_1m',
            'volume': 0
        }
        '''
        interval = self.normalize_candle_interval[msg['resolution']]
        c = Candle(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['symbol']),
            self.timestamp_normalize(msg['candle_start_time']),
            self.timestamp_normalize(msg['candle_start_time']) + timedelta_str_to_sec(interval) - 1,
            interval,
            None,
            Decimal(msg['open'] if msg['open'] else 0),
            Decimal(msg['close'] if msg['close'] else 0),
            Decimal(msg['high'] if msg['high'] else 0),
            Decimal(msg['low'] if msg['low'] else 0),
            Decimal(msg['volume'] if msg['volume'] else 0),
            False,
            self.timestamp_normalize(msg['timestamp']),
            raw=msg)
        await self.callback(CANDLES, c, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        '''
        {
            'buy': [
                {
                    'depth': '0.007755',
                    'limit_price': '55895.5',
                    'size': '0.007755'
                    },
                    ...
            ],
            'last_sequence_no': 1638135705586546,
            'last_updated_at': 1638135705559000,
            'product_id': 8320,
            'sell': [
                {
                    'depth': '0.008855',
                    'limit_price': '55901.5',
                    'size': '0.008855'
                },
                ...
            ],
            'symbol': 'BTC_USDT',
            'timestamp': 1638135705586546,
            'type': 'l2_orderbook'
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        if symbol not in self._l2_book:
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)

        self._l2_book[symbol].book.bids = {Decimal(e['limit_price']): Decimal(e['size']) for e in msg['buy']}
        self._l2_book[symbol].book.asks = {Decimal(e['limit_price']): Decimal(e['size']) for e in msg['sell']}
        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, timestamp=self.timestamp_normalize(msg['timestamp']), raw=msg)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['type'] == 'l2_orderbook':
            await self._book(msg, timestamp)
        elif msg['type'].startswith('all_trades'):
            await self._trades(msg, timestamp)
        elif msg['type'].startswith('candlestick'):
            await self._candles(msg, timestamp)
        elif msg['type'] == 'subscriptions':
            return
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        await conn.write(json.dumps({
            "type": "subscribe",
            "payload": {
                "channels": [
                    {
                        "name": c if c != 'candlestick_' else c + self.candle_interval_map[self.candle_interval],
                        "symbols": list(self.subscription[c])
                    } for c in self.subscription]
            }
        }))
