'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import logging
from decimal import Decimal
import time

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import L2_BOOK, L3_BOOK, BUY, SELL, BID, ASK, TRADES, TICKER, COINBASE
from cryptofeed.standards import timestamp_normalize, pair_exchange_to_std


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
        await self.callback(TICKER, feed=self.id,
                                     pair=pair_exchange_to_std(msg['product_id']),
                                     bid=Decimal(msg['best_bid']),
                                     ask=Decimal(msg['best_ask']),
                                     timestamp=timestamp_normalize(self.id, msg['time']))

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
        pair = pair_exchange_to_std(msg['product_id'])

        if 'full' in self.channels or ('full' in self.config and pair in self.config['full']):
            delta = {BID: [], ASK: []}
            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            size = Decimal(msg['size'])
            maker_order_id = msg['maker_order_id']
            timestamp = timestamp_normalize(self.id, msg['time'])

            _, new_size = self.order_map[maker_order_id]
            new_size -= size
            if new_size <= 0:
                del self.order_map[maker_order_id]
                delta[side].append((maker_order_id, price, 0))
                del self.l3_book[pair][side][price][maker_order_id]
                if len(self.l3_book[pair][side][price]) == 0:
                    del self.l3_book[pair][side][price]
            else:
                self.order_map[maker_order_id] = (price, new_size)
                self.l3_book[pair][side][price][maker_order_id] = new_size
                delta[side].append((maker_order_id, price, new_size))

            await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, timestamp)

        await self.callback(TRADES,
            feed=self.id,
            pair=pair_exchange_to_std(msg['product_id']),
            order_id=msg['trade_id'],
            side=SELL if msg['side'] == 'buy' else BUY,
            amount=Decimal(msg['size']),
            price=Decimal(msg['price']),
            timestamp=timestamp_normalize(self.id, msg['time'])

        )

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float):
        pair = pair_exchange_to_std(msg['product_id'])
        self.l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['asks']
            })
        }

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp)

    async def _pair_level2_update(self, msg: dict, timestamp: float):
        pair = pair_exchange_to_std(msg['product_id'])
        delta = {BID: [], ASK: []}
        for side, price, amount in msg['changes']:
            side = BID if side == 'buy' else ASK
            price = Decimal(price)
            amount = Decimal(amount)
            bidask = self.l2_book[pair][side]

            if amount == 0:
                del bidask[price]
                delta[side].append((price, 0))
            else:
                bidask[price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp)

    async def _book_snapshot(self, pairs: list):
        self.__reset()
        # Coinbase needs some time to send messages to us
        # before we request the snapshot. If we don't sleep
        # the snapshot seq no could be much earlier than
        # the subsequent messages, causing a seq no mismatch.
        await asyncio.sleep(2)

        url = 'https://api.pro.coinbase.com/products/{}/book?level=3'
        urls = [url.format(pair) for pair in pairs]

        results = []
        for url in urls:
            ret = requests.get(url)
            results.append(ret)

        timestamp = time.time()
        for res, pair in zip(results, pairs):
            orders = res.json()
            npair = pair_exchange_to_std(pair)
            self.l3_book[npair] = {BID: sd(), ASK: sd()}
            self.seq_no[npair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side + 's']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.l3_book[npair][side]:
                        self.l3_book[npair][side][price][order_id] = size
                    else:
                        self.l3_book[npair][side][price] = {order_id: size}
                    self.order_map[order_id] = (price, size)
            await self.book_callback(self.l3_book[npair], L3_BOOK, npair, True, None, timestamp=timestamp)

    async def _open(self, msg):
        delta = {BID: [], ASK: []}
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = pair_exchange_to_std(msg['product_id'])
        order_id = msg['order_id']
        timestamp = timestamp_normalize(self.id, msg['time'])

        if price in self.l3_book[pair][side]:
            self.l3_book[pair][side][price][order_id] = size
        else:
            self.l3_book[pair][side][price] = {order_id: size}
        self.order_map[order_id] = (price, size)

        delta[side].append((order_id, price, size))

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, timestamp)

    async def _done(self, msg):
        """
        per Coinbase API Docs:

        A done message will be sent for received orders which are fully filled or canceled due
        to self-trade prevention. There will be no open message for such orders. Done messages
        for orders which are not on the book should be ignored when maintaining a real-time order book.
        """
        delta = {BID: [], ASK: []}

        if 'price' not in msg:
            return

        order_id = msg['order_id']
        if order_id not in self.order_map:
            return

        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        pair = pair_exchange_to_std(msg['product_id'])
        timestamp = timestamp_normalize(self.id, msg['time'])

        del self.l3_book[pair][side][price][order_id]
        if len(self.l3_book[pair][side][price]) == 0:
            del self.l3_book[pair][side][price]
        delta[side].append((order_id, price, 0))
        del self.order_map[order_id]

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, timestamp)

    async def _change(self, msg):
        delta = {BID: [], ASK: []}

        if 'price' not in msg or not msg['price']:
            return
        timestamp = timestamp_normalize(self.id, msg['time'])
        order_id = msg['order_id']
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        pair = pair_exchange_to_std(msg['product_id'])

        self.l3_book[pair][side][price][order_id] = new_size
        self.order_map[order_id] = (price, new_size)

        delta[side].append((order_id, price, new_size))

        await self.book_callback(self.l3_book, L3_BOOK, pair, False, delta, timestamp)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'product_id' in msg and 'sequence' in msg and ('full' in self.channels or ('full' in self.config and msg['product_id'] in self.config['full'])):
            pair = pair_exchange_to_std(msg['product_id'])
            if msg['sequence'] <= self.seq_no[pair]:
                return
            elif ('full' in self.channels or 'full' in self.config) and msg['sequence'] != self.seq_no[pair] + 1:
                LOG.warning("%s: Missing sequence number detected for %s", self.id, pair)
                LOG.warning("%s: Requesting book snapshot", self.id)
                await self._book_snapshot(self.pairs or self.book_pairs)
                return

            self.seq_no[pair] = msg['sequence']

        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg)
            elif msg['type'] == 'match' or msg['type'] == 'last_match':
                await self._book_update(msg)
            elif msg['type'] == 'snapshot':
                await self._pair_level2_snapshot(msg, timestamp)
            elif msg['type'] == 'l2update':
                await self._pair_level2_update(msg, timestamp)
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
        snapshot = False
        self.book_pairs = []

        if self.config:
            for chan in self.config:
                await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": list(self.config[chan]),
                                         "channels": [chan]
                                         }))
                if 'full' in chan:
                    snapshot = True
                    self.book_pairs.extend(list(self.config[chan]))
        else:
            await websocket.send(json.dumps({"type": "subscribe",
                                            "product_ids": self.pairs,
                                            "channels": self.channels
                                            }))
        if 'full' in self.channels or snapshot:
            await self._book_snapshot(self.pairs or self.book_pairs)
