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
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(GDAX, self).__init__('wss://ws-feed.gdax.com')
        self.user_channels = channels
        # user ticker channel for trades and match for book
        channels_map = {'trades': 'ticker', 'book': 'level2'}
        self.channels = [channels_map.get(c, c) for c in channels]
        self.pairs = pairs
        self.book = {}
        self.level2 = {}
        self.order_map = {}
        self.seq_no = {}
        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None)}
        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def _ticker(self, msg):
        if 'ticker' in self.user_channels:
            await self.callbacks['ticker'](feed='gdax',
                                           pair=msg['product_id'],
                                           bid=Decimal(msg['best_bid']),
                                           ask=Decimal(msg['best_ask']))

    async def _agg_trades(self, msg):
        if 'trades' in self.user_channels and 'side' in msg:
            await self.callbacks['trades'](
                feed='gdax',
                pair=msg['product_id'],
                side=msg['side'], # I assume we always want the taker side?
                amount=msg['last_size'],
                price=msg['price']
            )

    async def _book_update(self, msg):
        # GDAX calls this 'match'
        # This will also be called when 'book' channels are enabled

        # TODO: Are we sure this is accurate? Wouldn't the level2 channel be better?
        if self.book:
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

            await self.callbacks['book'](feed='gdax', book=self.book)

    async def _pair_level2_snapshot(self, msg):
        # using a dict here is a bit strange, we need to sort it to use it
        # not that the count is not relevant here as we don't get updates about it
        self.level2[msg['product_id']] = {
            'bid': {
                float(price): {'count': None, 'amount': amount}
                for price, amount in msg['bids']
            },
            'ask': {
                float(price): {'count': None, 'amount': amount}
                for price, amount in msg['asks']
            }
        }

    async def _pair_level2_update(self, msg):
        for side, price, amount in msg['changes']:
            bidask =  self.level2[msg['product_id']]['bid' if side == 'buy' else 'ask']
            price = float(price)

            if amount == "0":
                if price in bidask:
                    del bidask[price]
            else:
                bidask.setdefault(price, {})['amount'] = float(amount)

        # Note having the book by pair would be more efficient
        await self.callbacks['book'](feed='gdax', book=self.level2)

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
        await self.callbacks['book'](feed='gdax', book=self.book)

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
        await self.callbacks['book'](feed='gdax', book=self.book)

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

        await self.callbacks['book'](feed='gdax', book=self.book)

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
                await asyncio.gather(self._ticker(msg), self._agg_trades(msg))
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
                print('Invalid message type {}'.format(msg))

    async def subscribe(self, websocket):
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
        if 'full' in self.channels:
            await self._book_snapshot()
