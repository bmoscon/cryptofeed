'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
import logging
from typing import Dict, Tuple

from yapic import json

from cryptofeed.defines import ASK, BID, FMFW as FMFW_id, L2_BOOK, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


class FMFW(Feed):
    id = FMFW_id
    symbol_endpoint = 'https://api.fmfw.io/api/3/public/symbol'
    websocket_channels = {
        L2_BOOK: 'orderbook/full',
        TRADES: 'trades',
        TICKER: 'ticker/1s',
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

    def __init__(self, **kwargs):
        super().__init__('wss://api.fmfw.io/api/3/ws/public', **kwargs)

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

    async def message_handler(self, msg: str, conn, ts: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'result' in msg:
            LOG.debug("%s: Info message from exchange: %s", conn.uuid, msg)
        elif msg['ch'] == 'orderbook/full':
            await self._book(msg, ts)
        
   
    async def subscribe(self, conn):
        self.__reset()

        for chan in self.subscription:
            await conn.write(json.dumps({"method": "subscribe",
                                         "params": {"symbols": self.subscription[chan]},
                                         "ch": chan,
                                         "id": 1234
                                         }))
