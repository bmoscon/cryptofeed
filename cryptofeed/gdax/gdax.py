'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
from decimal import Decimal

import requests

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback


class GDAX(Feed):
    def __init__(self, pairs=None, channels=None, callbacks={}):
        super(GDAX, self).__init__('wss://ws-feed.gdax.com')
        self.channels = channels
        self.pairs = pairs
        self.book = {}
        self.order_map = {}
        self.seq_no = {}
        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None)}
        for cb in callbacks:
            self.callbacks[cb] = callbacks[cb]
    
    async def _ticker(self, msg):
        await self.callbacks['ticker'](feed='gdax',
                                       pair=msg['product_id'],
                                       bid=msg['best_bid'],
                                       ask=msg['best_ask'])
    
    async def _trades(self, msg):
        # GDAX calls this 'match'
        # This will also be called when 'book' channels are enabled
        if self.book == {}:
            await self.callbacks['trades'](feed='gdax',
                                           pair=msg['product_id'],
                                           side=msg['side'],
                                           amount=msg['size'],
                                           price=msg['price'])
        else:
            price = Decimal(msg['price'])
            side = 'ask' if msg['side'] == 'sell' else 'bid'
            size = Decimal(msg['size'])
            pair = msg['product_id']
            maker_order_id = msg['maker_order_id']

            self.order_map[maker_order_id]['size'] -= size
            if self.order_map[maker_order_id]['size'] <= 0:
                del self.order_map[maker_order_id]

            self.book[pair][side][price] -= size
            if self.book[pair][side][price] == 0:
                del self.book[pair][side][price]

            await self.callbacks['book'](self.book)

    async def _book_snapshot(self):
        self.book = {}
        loop = asyncio.get_event_loop()
        url = 'https://api.gdax.com/products/{}/book?level=3'
        futures = [loop.run_in_executor(None, requests.get, url.format(pair)) for pair in self.pairs]
        results = [await future for future in futures]
        for res, pair in zip(results, self.pairs):
            orders = res.json()
            self.book[pair] = {'bid': {}, 'ask': {}}
            self.seq_no[pair] = orders['sequence']
            for side in ('bid', 'ask'):
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
        side = 'ask' if msg['side'] == 'sell' else 'bid'
        size = Decimal(msg['remaining_size'])
        pair = msg['product_id']
        order_id = msg['order_id']

        if price in self.book[pair][side]:
            self.book[pair][side][price] += size
        else:
            self.book[pair][side][price] = size

        self.order_map[order_id] = {'price': price, 'size': size}
        await self.callbacks['book'](self.book)
    
    async def _done(self, msg):
        if 'price' not in msg:
            return
        order_id = msg['order_id']
        if order_id not in self.order_map:
            return
        price = Decimal(msg['price'])
        side = 'ask' if msg['side'] == 'sell' else 'bid'
        pair = msg['product_id']

        size = self.order_map[order_id]['size']

        if self.book[pair][side][price] - size == 0:
            del self.book[pair][side][price]
        else:
            self.book[pair][side][price] -= size

        del self.order_map[order_id]
        await self.callbacks['book'](self.book)

    async def _change(self, msg):
        order_id = msg['order_id']
        if order_id not in self.order_map:
            return
        price = Decimal(msg['price'])
        side = 'ask' if msg['side'] == 'sell' else 'bid'
        new_size = Decimal(msg['new_size'])
        old_size = Decimal(msg['old_size'])
        pair = msg['product_id']

        size = old_size - new_size
        self.book[pair][side][price] -= size
        self.order_map[order_id] = new_size

        await self.callbacks['book'](self.book)

    async def message_handler(self, msg):
        msg = json.loads(msg)
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
                await self._trades(msg)
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
                print('Invalid message type {}'.format(msg))

    async def subscribe(self, websocket):
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
        if 'full' in self.channels:
            await self._book_snapshot()
