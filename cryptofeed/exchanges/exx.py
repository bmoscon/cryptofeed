'''
Copyright (C) 2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY
from cryptofeed.defines import EXX as EXX_id
from cryptofeed.defines import L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger('feedhandler')


class EXX(Feed):
    id = EXX_id
    symbol_endpoint = "https://api.exx.com/data/v1/tickers"
    websocket_channels = {
        L2_BOOK: 'ENTRUST_ADD',
        TRADES: 'TRADE',
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        exchange = [key.upper() for key in data.keys()]
        for sym in exchange:
            b, q = sym.split("_")
            s = Symbol(b, q)
            ret[s.normalized] = sym
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://ws.exx.com/websocket', **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _book_update(self, msg: dict, timestamp: float):
        """
        Snapshot:

        [
            [
                'AE',
                '1',
                'BTC_USDT',
                '1547941504',
                {
                    'asks':[
                        [
                        '25000.00000000',
                        '0.02000000'
                        ],
                        [
                        '19745.83000000',
                        '0.00200000'
                        ],
                        [
                        '19698.96000000',
                        '0.00100000'
                        ],
                        ...
                    ]
                },
                {
                    'bids':[
                        [
                        '3662.83040000',
                        '0.00100000'
                        ],
                        [
                        '3662.77540000',
                        '0.01000000'
                        ],
                        [
                        '3662.59900000',
                        '0.10300000'
                        ],
                        ...
                    ]
                }
            ]
        ]


        Update:

        ['E', '1', '1547942636', 'BTC_USDT', 'ASK', '3674.91740000', '0.02600000']
        """
        delta = {BID: [], ASK: []}
        if msg[0] == 'AE':
            # snapshot
            delta = None
            pair = self.exchange_symbol_to_std_symbol(msg[2])
            ts = msg[3]
            asks = msg[4]['asks'] if 'asks' in msg[4] else msg[5]['asks']
            bids = msg[5]['bids'] if 'bids' in msg[5] else msg[4]['bids']
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            self._l2_book[pair].book.bids = {Decimal(price): Decimal(amount) for price, amount in bids}
            self._l2_book[pair].book.asks = {Decimal(price): Decimal(amount) for price, amount in asks}
        else:
            # Update
            ts = msg[2]
            pair = self.exchange_symbol_to_std_symbol(msg[3])
            side = ASK if msg[4] == 'ASK' else BID
            price = Decimal(msg[5])
            amount = Decimal(msg[6])

            if amount == 0:
                if price in self._l2_book[pair].book[side]:
                    del self._l2_book[pair][side].book[price]
                    delta[side].append((price, 0))
            else:
                self._l2_book[pair].book[side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=ts, raw=msg, delta=delta)

    async def _trade(self, msg: dict, timestamp: float):
        """
        Trade message

        ['T', '1', '1547947390', 'BTC_USDT', 'bid', '3683.74440000', '0.082', '33732290']
        """
        pair = self.exchange_symbol_to_std_symbol(msg[3])

        t = Trade(
            self.id,
            pair,
            BUY if msg[4] == 'bid' else SELL,
            Decimal(msg[6]),
            Decimal(msg[5]),
            float(msg[2]),
            id=msg[7],
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg[0], list):
            msg = msg[0]

        if msg[0] == 'E' or msg[0] == 'AE':
            await self._book_update(msg, timestamp)
        elif msg[0] == 'T':
            await self._trade(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                await conn.write(json.dumps({"dataType": f"1_{chan}_{pair}",
                                             "dataSize": 50,
                                             "action": "ADD"
                                             }))
