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

from cryptofeed.defines import BUY, CALL, CANDLES, DELTA, FUTURES, L2_BOOK, OPTION, PERPETUAL, PUT, SELL, SPOT, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Trade, Ticker, Candle, OrderBook


LOG = logging.getLogger('feedhandler')


class Delta(Feed):
    id = DELTA
    symbol_endpoint = 'https://api.delta.exchange/v2/products'
    websocket_channels = {
        L2_BOOK: 'book',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candlestick'
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

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
            elif entry['contract_type'] in {'interest_rate_swaps', 'spreads'}:
                continue
            else:
                raise ValueError(entry['contract_type'])

            info['instrument_type'][sym.normalized] = sym.type
            info['tick_size'][sym.normalized] = entry['tick_size']
            ret[sym.normalized] = entry['symbol']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://socket.delta.exchange', **kwargs)
        if self.sandbox:
            self.address = 'wss://testnet-socket.delta.exchange'
        self.__reset()

    def __reset(self):
        self._l2_book = {}
