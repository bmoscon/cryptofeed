'''
Copyright (C) 2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY
from cryptofeed.defines import EXX as EXX_id
from cryptofeed.defines import L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class EXX(Feed):
    id = EXX_id
    symbol_endpoint = "https://api.exx.com/data/v1/tickers"

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        exchange = [key.upper() for key in data.keys()]
        symbols = [key.replace("_", symbol_separator) for key in exchange]
        return dict(zip(symbols, exchange)), {}

    def __init__(self, **kwargs):
        super().__init__('wss://ws.exx.com/websocket', **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

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
        forced = False
        delta = {BID: [], ASK: []}
        if msg[0] == 'AE':
            # snapshot
            forced = True
            pair = self.exchange_symbol_to_std_symbol(msg[2])
            ts = msg[3]
            asks = msg[4]['asks'] if 'asks' in msg[4] else msg[5]['asks']
            bids = msg[5]['bids'] if 'bids' in msg[5] else msg[4]['bids']
            self.l2_book[pair] = {
                BID: sd({
                    Decimal(price): Decimal(amount)
                    for price, amount in bids
                }),
                ASK: sd({
                    Decimal(price): Decimal(amount)
                    for price, amount in asks
                })
            }
        else:
            # Update
            ts = msg[2]
            pair = self.exchange_symbol_to_std_symbol(msg[3])
            side = ASK if msg[4] == 'ASK' else BID
            price = Decimal(msg[5])
            amount = Decimal(msg[6])

            if amount == 0:
                if price in self.l2_book[pair][side]:
                    del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
            else:
                self.l2_book[pair][side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, ts, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        Trade message

        ['T', '1', '1547947390', 'BTC_USDT', 'bid', '3683.74440000', '0.082', '33732290']
        """
        ts = float(msg[2])
        pair = self.exchange_symbol_to_std_symbol(msg[3])
        side = BUY if msg[4] == 'bid' else SELL
        price = Decimal(msg[5])
        amount = Decimal(msg[6])
        trade_id = msg[7]

        await self.callback(TRADES,
                            feed=self.id,
                            symbol=pair,
                            order_id=trade_id,
                            side=side,
                            amount=amount,
                            price=price,
                            timestamp=ts,
                            receipt_timestamp=timestamp,
                            )

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
