'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import asyncio
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_exchange_to_std, std_channel_to_exchange, pair_std_to_exchange


class Bitstamp(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(Bitstamp, self).__init__(
            'wss://ws.pusherapp.com/app/de504dc5763aeef9ff52?protocol=7&client=js&version=2.1.6&flash=false'
        )

        self.channels = channels
        self.pairs = pairs
        self.book = {}
        self.seq_no = {}
        self.snapshot_processed = False
        self.callbacks = {
            'trades': Callback(None),
            'ticker': Callback(None),
            'book': Callback(None)
        }

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def _process_snapshot(self):
        self.book = {}
        loop = asyncio.get_event_loop()
        btc_usd_url = 'https://www.bitstamp.net/api/order_book/'
        url = 'https://www.bitstamp.net/api/v2/order_book/{}/'
        pairs =  [pair_std_to_exchange(pair, 'BITSTAMP') for pair in self.pairs]
        futures = [loop.run_in_executor(None, requests.get, url.format(pair) if pair != 'BTC-USD' else btc_usd_url) for pair in pairs]

        results = []
        for future in futures:
            ret = await future
            results.append(ret)

        for res, pair in zip(results, self.pairs):
            orders = res.json()
            self.book[pair] = {'bid': sd(), 'ask': sd()}
            self.seq_no[pair] = orders['timestamp']
            for side in ('bid', 'ask'):
                for price, size in orders[side+'s']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.book[pair][side]:
                        self.book[pair][side][price] += size
                    else:
                        self.book[pair][side][price] = size
        self.snapshot_processed = True

    async def _order_book(self, msg):
        if not self.snapshot_processed:
            await self._process_snapshot()
        data = msg['data']
        chan = msg['channel']
        pair = None
        if chan == 'diff_order_book':
            pair = 'BTC-USD'
        else:
            pair = pair_exchange_to_std(chan.split('_')[-1])

        if pair in self.seq_no:
            if data['timestamp'] <= self.seq_no[pair]:
                return
            else:
                del self.seq_no[pair]

        sides = ('bid', 'ask')
        for side in sides:
            for price, size in data[side+'s']:
                price = Decimal(price)
                size = Decimal(size)
                if size == 0:
                    if price in self.book[pair][side]:
                        del self.book[pair][side][price]
                else:
                    self.book[pair][side][price] = size
        await self.callbacks['book'](feed='bitstamp', book=self.book)

    async def _trades(self, msg):
        data = msg['data']
        chan = msg['channel']
        pair = None
        if chan == 'live_trades':
            pair = 'BTC-USD'
        else:
            pair = pair_exchange_to_std(chan.split('_')[-1])

        side = 'BUY' if data['type'] == 0 else 'SELL'
        amount = Decimal(data['amount'])
        price = Decimal(data['price'])
        await self.callbacks['trades'](feed='bitstamp',
                                       pair=pair,
                                       side=side,
                                       amount=amount,
                                       price=price)

    async def message_handler(self, msg):
        # for some reason the internal parts of the message
        # are formatted in such a way that it wont parse from
        # string to json without stripping some extra quotes and
        # slashes
        msg = msg.replace("\\", '')
        msg = msg.replace("\"{", "{")
        msg = msg.replace("}\"", "}")
        msg = json.loads(msg)
        if 'pusher' in msg['event']:
            if msg['event'] == 'pusher:connection_established':
                pass
            elif msg['event'] == 'pusher_internal:subscription_succeeded':
                pass
            else:
                print("Unexpected pusher message {}".format(msg))
        elif msg['event'] == 'trade':
            await self._trades(msg)
        elif msg['event'] == 'data':
            await self._order_book(msg)
        else:
            print('Invalid message type {}'.format(msg))

    async def subscribe(self, websocket):
        # if channel is order book we need to subscribe to the diff channel
        # to get updates, hit the REST endpoint to get the current complete state,
        # then process the updates from the diff channel, ignoring any updates that
        # are pre-timestamp on the response from the REST endpoint
        for channel in self.channels:
            channel = std_channel_to_exchange(channel, 'BITSTAMP')
            for pair in self.pairs:
                pair = pair_std_to_exchange(pair, 'BITSTAMP')
                await websocket.send(
                    json.dumps({
                        "event": "pusher:subscribe",
                        "data": {
                            "channel": "{}_{}".format(channel, pair) if pair != 'btcusd' else channel
                        }
                    }))
