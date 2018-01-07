'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange


class Gemini(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        if len(pairs) != 1:
            raise ValueError("Gemini requires a websocket per trading pair")
        if channels is not None:
            raise ValueError("Gemini does not support different channels")
        self.pair = pairs[0]
        super(Gemini, self).__init__('wss://api.gemini.com/v1/marketdata/' + pair_std_to_exchange(self.pair, 'GEMINI'))
        self.book = {self.pair: {'bid': {}, 'ask': {}}}
        self.callbacks = {'trades': Callback(None),
                          'book': Callback(None)}
        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def _book(self, msg):
        side = msg['side']
        price = Decimal(msg['price'])
        remaining = Decimal(msg['remaining'])
        #delta = Decimal(msg['delta'])

        if msg['reason'] == 'initial':
            self.book[self.pair][side][price] = remaining
        else:
            if remaining == 0:
                del self.book[self.pair][side][price]
            else:
                self.book[self.pair][side][price] = remaining
        await self.callbacks['book'](feed='gemini', book=self.book)


    async def _auction(self, msg):
        pass

    async def _trade(self, msg):
        price = Decimal(msg['price'])
        side = msg['makerSide']
        amount = Decimal(msg['amount'])
        await self.callbacks['trades'](feed='gemini', pair=self.pair, side=side, amount=amount, price=price)

    async def _update(self, msg):
        for update in msg['events']:
            if update['type'] == 'change':
                await self._book(update)
            elif update['type'] == 'trade':
                await self._trade(update)
            elif update['type'] == 'auction':
                await self._auction(update)
            else:
                print("Invalid update received {}".format(update))

    async def message_handler(self, msg):
        msg = json.loads(msg)
        if msg['type'] == 'update':
            await self._update(msg)
        elif msg['type'] == 'heartbeat':
            pass
        else:
            print('Invalid message type {}'.format(msg))

    async def subscribe(self, *args):
        return
