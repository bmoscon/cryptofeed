'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import logging
from decimal import Decimal
from collections import defaultdict

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.exchanges import GDAX as GDAX_ID
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, TRADES, TICKER, ADD, DEL, UPD, BOOK_DELTA


LOG = logging.getLogger('feedhandler')


class GDAX(Feed):
    id = GDAX_ID

    def __init__(self, pairs=None, channels=None, callbacks=None):
        super().__init__('wss://ws-feed.gdax.com', pairs=pairs, channels=channels, callbacks=callbacks)
        self.order_map = {}
        self.seq_no = {}
        self.book = {}

    async def _ticker(self, msg):
        '''
        {
            'type': 'ticker',
            'sequence': 5928281084,
            'product_id': 'BTC-USD',
            'price': '8500.01000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.1293778',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93594133',
            'best_bid': '8500',
            'best_ask': '8500.01'
        }

        {
            'type': 'ticker',
            'sequence': 5928281348,
            'product_id': 'BTC-USD',
            'price': '8500.00000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.13179472',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93835825',
            'best_bid': '8500',
            'best_ask': '8500.01',
            'side': 'sell',
            'time': '2018-05-21T00:30:11.587000Z',
            'trade_id': 43736677,
            'last_size': '0.00241692'
        }
        '''
        await self.callbacks[TICKER](feed=self.id,
                                     pair=msg['product_id'],
                                     bid=Decimal(msg['best_bid']),
                                     ask=Decimal(msg['best_ask']))

    async def _book_update(self, msg):
        '''
        {
            'type': 'match', or last_match
            'trade_id': 43736593
            'maker_order_id': '2663b65f-b74e-4513-909d-975e3910cf22',
            'taker_order_id': 'd058d737-87f1-4763-bbb4-c2ccf2a40bde',
            'side': 'buy',
            'size': '0.01235647',
            'price': '8506.26000000',
            'product_id': 'BTC-USD',
            'sequence': 5928276661,
            'time': '2018-05-21T00:26:05.585000Z'
        }
        '''
        if self.book:
            delta = {BID: defaultdict(list), ASK: defaultdict(list)}
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
                delta[side][DEL].append(price)
            else:
                delta[side][UPD].append((price, self.book[pair][side][price]))

            if self.do_deltas and self.updates < self.book_update_interval:
                self.updates += 1
                await self.callbacks[BOOK_DELTA](feed=self.id, pair=pair, delta=delta)

            if self.updates >= self.book_update_interval or not self.do_deltas:
                self.updates = 0
                await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

        await self.callbacks[TRADES](
                feed=self.id,
                pair=msg['product_id'],
                id=msg['trade_id'],
                side=BID if msg['side'] == 'buy' else ASK,
                amount=msg['size'],
                price=msg['price'],
                timestamp=msg['time']
            )

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

            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _open(self, msg):
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
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

        delta[side][ADD].append((price, size))

        if self.do_deltas and self.updates < self.book_update_interval:
            self.updates += 1
            await self.callbacks[BOOK_DELTA](feed=self.id, pair=pair, delta=delta)

        if self.updates >= self.book_update_interval or not self.do_deltas:
            self.updates = 0
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _done(self, msg):
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}

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
            delta[side][DEL].append(price)
        else:
            self.book[pair][side][price] -= size
            delta[side][UPD].append((price, self.book[pair][side][price]))

        del self.order_map[order_id]

        if self.do_deltas and self.updates < self.book_update_interval:
            self.updates += 1
            await self.callbacks[BOOK_DELTA](feed=self.id, pair=pair, delta=delta)

        if self.updates >= self.book_update_interval or not self.do_deltas:
            self.updates = 0
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def _change(self, msg):
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}

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

        delta[side][UPD].append((price, new_size))

        if self.do_deltas and self.updates < self.book_update_interval:
            self.updates += 1
            await self.callbacks[BOOK_DELTA](feed=self.id, pair=pair, delta=delta)

        if self.updates >= self.book_update_interval or not self.do_deltas:
            self.updates = 0
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.book[pair])

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'full' in self.channels and 'product_id' in msg and 'sequence' in msg:
            pair = msg['product_id']
            if pair not in self.seq_no:
                self.seq_no[pair] = msg['sequence']
            elif msg['sequence'] <= self.seq_no[pair]:
                return
            elif 'full' in self.channels and msg['sequence'] != self.seq_no[pair] + 1:
                LOG.warning("Missing sequence number detected")
                LOG.warning("Requesting book snapshot")
                await self._book_snapshot()
                return

            self.seq_no[pair] = msg['sequence']


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
