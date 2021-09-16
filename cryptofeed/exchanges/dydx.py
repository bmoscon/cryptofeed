'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, DYDX, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.exchanges.mixins.dydx_rest import dYdXRestMixin
from cryptofeed.types import OrderBook, Trade

LOG = logging.getLogger('feedhandler')


class dYdX(Feed, dYdXRestMixin):
    id = DYDX
    symbol_endpoint = 'https://api.dydx.exchange/v3/markets'
    websocket_channels = {
        L2_BOOK: 'v3_orderbook',
        TRADES: 'v3_trades',
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for symbol, entry in data['markets'].items():
            if entry['status'] != 'ONLINE':
                continue
            s = Symbol(entry['baseAsset'], entry['quoteAsset'])
            ret[s.normalized] = symbol
            info['tick_size'][s.normalized] = entry['tickSize']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://api.dydx.exchange/v3/ws', **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
        self.offsets = {}

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['id'])
        delta = {BID: [], ASK: []}

        if msg['type'] == 'channel_data':
            for side, data in msg['contents'].items():
                if side == 'offset':
                    offset = int(data)
                    continue
                side = BID if side == 'bids' else ASK
                for entry in data:
                    price = Decimal(entry[0])
                    amount = Decimal(entry[1])

                    if price in self.offsets[pair] and offset <= self.offsets[pair][price]:
                        continue

                    self.offsets[pair][price] = offset
                    if amount == 0:
                        if price in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][price]
                        delta[side].append((price, 0))
                    else:
                        self._l2_book[pair].book[side][price] = amount
                        delta[side].append((price, amount))
        else:
            # snapshot
            delta = None
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            self.offsets[pair] = {}

            for side, data in msg['contents'].items():
                side = BID if side == 'bids' else ASK
                for entry in data:
                    self.offsets[pair][Decimal(entry['price'])] = int(entry['offset'])
                    size = Decimal(entry['size'])
                    if size > 0:
                        self._l2_book[pair].book[side][Decimal(entry['price'])] = size

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta, raw=msg)

    async def _trade(self, msg: dict, timestamp: float):
        """
        update:
        {
           'type': 'channel_data',
           'connection_id': '7b4abf85-f9eb-4f6e-82c0-5479ad5681e9',
           'message_id': 18,
           'id': 'DOGE-USD',
           'channel': 'v3_trades',
           'contents': {
               'trades': [{
                   'size': '390',
                   'side': 'SELL',
                   'price': '0.2334',
                   'createdAt': datetime.datetime(2021, 6, 23, 22, 36, 34, 520000, tzinfo=datetime.timezone.utc)
                }]
            }
        }

        initial message:
        {
            'type': 'subscribed',
            'connection_id': 'ccd8b74c-97b3-491d-a9fc-4a92a171296e',
            'message_id': 4,
            'channel': 'v3_trades',
            'id': 'UNI-USD',
            'contents': {
                'trades': [{
                    'side': 'BUY',
                    'size': '384.1',
                    'price': '17.23',
                    'createdAt': datetime.datetime(2021, 6, 23, 20, 28, 25, 465000, tzinfo=datetime.timezone.utc)
                },
                {
                    'side': 'SELL',
                    'size': '384.1',
                    'price': '17.138',
                    'createdAt': datetime.datetime(2021, 6, 23, 20, 22, 26, 466000, tzinfo=datetime.timezone.utc)},
               }]
            }
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['id'])
        for trade in msg['contents']['trades']:
            t = Trade(
                self.id,
                pair,
                BUY if trade['side'] == 'BUY' else SELL,
                Decimal(trade['size']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['createdAt']),
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['type'] == 'channel_data' or msg['type'] == 'subscribed':
            chan = self.exchange_channel_to_std(msg['channel'])
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
                msg = {"type": "subscribe", "channel": chan, "id": symbol}
                if self.exchange_channel_to_std(chan) == L2_BOOK:
                    msg['includeOffsets'] = True
                await conn.write(json.dumps(msg))
