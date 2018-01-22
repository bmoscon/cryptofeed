'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

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
        self.callbacks = {
            'trades': Callback(None),
            'ticker': Callback(None),
            'book': Callback(None)
        }

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]
    
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
        else:
            print('Invalid message type {}'.format(msg))



    async def subscribe(self, websocket):
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
