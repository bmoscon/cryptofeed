'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import logging
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.exchanges import GDAX as GDAX_ID
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, TRADES, TICKER


LOG = logging.getLogger('feedhandler')


class GDAX(Feed):
    id = GDAX_ID

    def __init__(self, pairs=None, channels=None, callbacks=None):
        super().__init__('wss://ws-feed.gdax.com', pairs=pairs, channels=channels, callbacks=callbacks)
        self.order_map = {}
        self.seq_no = {}

    async def _ticker(self, msg):
        await self.callbacks[TICKER](feed=self.id,
                                     pair=msg['product_id'],
                                     bid=Decimal(msg['best_bid']),
                                     ask=Decimal(msg['best_ask']))
        if 'side' in msg:
            await self.callbacks[TRADES](
                feed=self.id,
                pair=msg['product_id'],
                side=ASK if msg['side'] == 'sell' else BID,
                amount=msg['last_size'],
                price=msg['price']
            )

    async def _book_update(self, msg):
        # GDAX calls this 'match'
        if self.book:
            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            size = Decimal(msg['size'])
            pair = msg['product_id']
            maker_order_id = msg['maker_order_id']

            self.order_map[maker_order_id]['size'] -= size
            if self.order_map[maker_order_id]['size'] <= 0:
                del self.order_map[maker_order_id]

            self.book[pair][side][price] -= size
            if self.book[pair][side][price] == 0:
                del self.book[pair][side][price]

            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _pair_level2_snapshot(self, msg):
        self.l2_book[msg['product_id']] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['asks']
            })
        }

    async def _pair_level2_update(self, msg):
        for side, price, amount in msg['changes']:
            price = Decimal(price)
            amount = Decimal(amount)
            bidask = self.l2_book[msg['product_id']][BID if side == 'buy' else ASK]

            if amount == "0":
                if price in bidask:
                    del bidask[price]
            else:
                bidask[price] = amount

        await self.callbacks[L2_BOOK](feed=self.id, pair=msg['product_id'], book=self.l2_book[msg['product_id']])

    async def _book_snapshot(self):
        self.book = {}
        loop = asyncio.get_event_loop()
        url = 'https://api.gdax.com/products/{}/book?level=3'
        futures = [loop.run_in_executor(None, requests.get, url.format(pair)) for pair in self.pairs]

        results = []
        for future in futures:
            ret = await future
            results.append(ret)

        for res, pair in zip(results, self.pairs):
            orders = res.json()
            self.book[pair] = {BID: sd(), ASK: sd()}
            self.seq_no[pair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side+'s']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.book[pair][side]:
                        self.book[pair][side][price] += size
                    else:
                        self.book[pair][side][price] = size
                    self.order_map[order_id] = {'price': price, 'size': size}

    async def _open(self, msg):
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = msg['product_id']
        order_id = msg['order_id']

        if price in self.book[pair][side]:
            self.book[pair][side][price] += size
        else:
            self.book[pair][side][price] = size

        self.order_map[order_id] = {'price': price, 'size': size}
        await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _done(self, msg):
        if 'price' not in msg:
            return
        order_id = msg['order_id']
        if order_id not in self.order_map:
            return
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        pair = msg['product_id']

        size = self.order_map[order_id]['size']

        if self.book[pair][side][price] - size == 0:
            del self.book[pair][side][price]
        else:
            self.book[pair][side][price] -= size

        del self.order_map[order_id]
        await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _change(self, msg):
        order_id = msg['order_id']
        if order_id not in self.order_map:
            return
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        old_size = Decimal(msg['old_size'])
        pair = msg['product_id']

        size = old_size - new_size
        self.book[pair][side][price] -= size
        self.order_map[order_id] = new_size

        await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'product_id' in msg and 'sequence' in msg:
            if msg['product_id'] in self.seq_no:
                if msg['sequence'] < self.seq_no[msg['product_id']]:
                    return
                else:
                    del self.seq_no[msg['product_id']]

        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg)
            elif msg['type'] == 'match' or msg['type'] == 'last_match':
                await self._book_update(msg)
            elif msg['type'] == 'snapshot':
                await self._pair_level2_snapshot(msg)
            elif msg['type'] == 'l2update':
                await self._pair_level2_update(msg)
            elif msg['type'] == 'open':
                await self._open(msg)
            elif msg['type'] == 'done':
                await self._done(msg)
            elif msg['type'] == 'change':
                await self._change(msg)
            elif msg['type'] == 'received':
                pass
            elif msg['type'] == 'activate':
                pass
            elif msg['type'] == 'subscriptions':
                pass
            else:
                LOG.warning('{} - Invalid message type {}'.format(self.id, msg))

    async def subscribe(self, websocket):
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
        if 'full' in self.channels:
            await self._book_snapshot()
