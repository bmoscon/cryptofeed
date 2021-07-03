'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, CANDLES, PHEMEX, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import normalize_channel, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Phemex(Feed):
    id = PHEMEX
    symbol_endpoint = 'https://api.phemex.com/exchange/public/cfg/v2/products'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']['products']:
            if entry['status'] != 'Listed':
                continue
            normalized = entry['settleCurrency'] + symbol_separator + entry['quoteCurrency']
            ret[normalized] = entry['symbol']
            info['tick_size'][normalized] = entry['tickSize']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://phemex.com/ws', **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        await self.callback(TRADES,
                            feed=self.id,
                            order_id=None,
                            symbol=pair,
                            side=BUY if trade['side'] == 'BUY' else SELL,
                            amount=Decimal(trade['size']),
                            price=Decimal(trade['price']),
                            timestamp=timestamp_normalize(self.id, trade['createdAt']),
                            receipt_timestamp=timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['type'] == 'channel_data' or msg['type'] == 'subscribed':
            chan = normalize_channel(self.id, msg['channel'])
            if chan == L2_BOOK:
                await self._book(msg, timestamp)
            elif chan == TRADES:
                await self._trade(msg, timestamp)
            else:
                LOG.warning("%s: unexpected channel type received: %s", self.id, msg)
        elif msg['type'] == 'connected':
            return
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        for chan, symbols in self.subscription.items():
            for symbol in symbols:
                msg = {"id": 1, "method": chan, "params": symbols}

                if normalize_channel(self.id, chan) == CANDLES:
                    pass
                await conn.write(json.dumps(msg))
