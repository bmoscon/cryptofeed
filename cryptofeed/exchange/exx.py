'''
Copyright (C) 2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.standards import pair_exchange_to_std
from cryptofeed.defines import EXX as EXX_id
from cryptofeed.defines import L2_BOOK, BUY, SELL, BID, ASK, TRADES


LOG = logging.getLogger('feedhandler')


class EXX(Feed):
    id = EXX_id

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ws.exx.com/websocket', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _book_update(self, msg):
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
            pair = pair_exchange_to_std(msg[2])
            timestamp = msg[3]
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
            timestamp = msg[2]
            pair = pair_exchange_to_std(msg[3])
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

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp)

    async def _trade(self, msg):
        """
        Trade message

        ['T', '1', '1547947390', 'BTC_USDT', 'bid', '3683.74440000', '0.082', '33732290']
        """
        timestamp = float(msg[2])
        pair = pair_exchange_to_std(msg[3])
        side = BUY if msg[4] == 'bid' else SELL
        price = Decimal(msg[5])
        amount = Decimal(msg[6])
        trade_id = msg[7]

        await self.callback(TRADES,
            feed=self.id,
            pair=pair,
            order_id=trade_id,
            side=side,
            amount=amount,
            price=price,
            timestamp=timestamp
        )

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg[0], list):
            msg = msg[0]

        if msg[0] == 'E' or msg[0] == 'AE':
            await self._book_update(msg)
        elif msg[0] == 'T':
            await self._trade(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        for channel in self.channels if not self.config else self.config:
            for pair in self.pairs if not self.config else self.config[channel]:
                await websocket.send(json.dumps({"dataType": f"1_{channel}_{pair}",
                                                 "dataSize": 50,
                                                 "action": "ADD"
                                                 }))
