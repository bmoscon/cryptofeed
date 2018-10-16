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
from datetime import datetime as dt

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.exchanges import COINBASE
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, TRADES, TICKER, DEL, UPD


LOG = logging.getLogger('feedhandler')


class Coinbase(Feed):
    id = COINBASE

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://ws-feed.pro.coinbase.com', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.order_map = {}
        self.seq_no = {}
        self.l3_book = {}
        self.l2_book = {}

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
        if self.l3_book:
            delta = {BID: defaultdict(list), ASK: defaultdict(list)}
            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            size = Decimal(msg['size'])
            pair = msg['product_id']
            maker_order_id = msg['maker_order_id']
            timestamp = msg['time']

            _, new_size = self.order_map[maker_order_id]
            new_size -= size
            if new_size <= 0:
                del self.order_map[maker_order_id]
                delta[side][DEL].append((maker_order_id, price))
                del self.l3_book[pair][side][price][maker_order_id]
                if len(self.l3_book[pair][side][price]) == 0:
                    del self.l3_book[pair][side][price]
            else:
                self.order_map[maker_order_id] = (price, new_size)
                self.l3_book[pair][side][price][maker_order_id] = new_size
                delta[side][UPD].append((maker_order_id, price, new_size))

            await self.book_callback(pair, L3_BOOK, False, delta, timestamp)

        await self.callbacks[TRADES](
                feed=self.id,
                pair=msg['product_id'],
                order_id=msg['trade_id'],
                side=BID if msg['side'] == 'buy' else ASK,
                amount=msg['size'],
                price=msg['price'],
                timestamp=msg['time']
            )

    async def _pair_level2_snapshot(self, msg):
        timestamp = dt.utcnow()
        timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
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

        await self.book_callback(msg['product_id'], L2_BOOK, True, None, timestamp)

    async def _pair_level2_update(self, msg):
        timestamp = dt.utcnow()
        timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        for side, price, amount in msg['changes']:
            side = BID if side == 'buy' else ASK
            price = Decimal(price)
            amount = Decimal(amount)
            bidask = self.l2_book[msg['product_id']][side]

            if amount == 0:
                del bidask[price]
                delta[side][DEL].append(price)
            else:
                bidask[price] = amount
                delta[side][UPD].append((price, amount))

        await self.book_callback(msg['product_id'], L2_BOOK, False, delta, timestamp)

    async def _book_snapshot(self):
        self.__reset()
        loop = asyncio.get_event_loop()
        url = 'https://api.pro.coinbase.com/products/{}/book?level=3'
        futures = [loop.run_in_executor(None, requests.get, url.format(pair)) for pair in self.pairs]

        results = []
        for future in futures:
            ret = await future
            results.append(ret)

        for res, pair in zip(results, self.pairs):
            orders = res.json()
            self.l3_book[pair] = {BID: sd(), ASK: sd()}
            self.seq_no[pair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side+'s']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.l3_book[pair][side]:
                        self.l3_book[pair][side][price][order_id] = size
                    else:
                        self.l3_book[pair][side][price] = {order_id: size}
                    self.order_map[order_id] = (price, size)
            timestamp = dt.utcnow()
            timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l3_book[pair], timestamp=timestamp)

    async def _open(self, msg):
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = msg['product_id']
        order_id = msg['order_id']
        timestamp = msg['time']


        if price in self.l3_book[pair][side]:
            self.l3_book[pair][side][price][order_id] = size
        else:
            self.l3_book[pair][side][price] = {order_id: size}
        self.order_map[order_id] = (price, size)

        delta[side][UPD].append((order_id, price, size))

        await self.book_callback(pair, L3_BOOK, False, delta, timestamp)

    async def _done(self, msg):
        """
        per Coinbase API Docs:

        A done message will be sent for received orders which are fully filled or canceled due
        to self-trade prevention. There will be no open message for such orders. Done messages
        for orders which are not on the book should be ignored when maintaining a real-time order book.
        """
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}

        if 'price' not in msg:
            return

        order_id = msg['order_id']
        if order_id not in self.order_map:
            return

        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        pair = msg['product_id']
        timestamp = msg['time']

        del self.l3_book[pair][side][price][order_id]
        if len(self.l3_book[pair][side][price]) == 0:
            del self.l3_book[pair][side][price]
        delta[side][DEL].append((order_id, price))
        del self.order_map[order_id]

        await self.book_callback(pair, L3_BOOK, False, delta, timestamp)

    async def _change(self, msg):
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}

        if 'price' not in msg or not msg['price']:
            return
        timestamp = msg['time']
        order_id = msg['order_id']
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        pair = msg['product_id']

        self.l3_book[pair][side][price][order_id] = new_size
        self.order_map[order_id] = (price, new_size)

        delta[side][UPD].append((order_id, price, new_size))

        await self.book_callback(pair, L3_BOOK, False, delta, timestamp)

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'full' in self.channels and 'product_id' in msg and 'sequence' in msg:
            pair = msg['product_id']
            if msg['sequence'] <= self.seq_no[pair]:
                return
            elif 'full' in self.channels and msg['sequence'] != self.seq_no[pair] + 1:
                LOG.warning("%s: Missing sequence number detected", self.id)
                LOG.warning("%s: Requesting book snapshot", self.id)
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
                LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
        if 'full' in self.channels:
            await self._book_snapshot()
