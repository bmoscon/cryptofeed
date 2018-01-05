'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std, std_channel_to_exchange


class HitBTC(Feed):
    def __init__(self, pairs=None, channels=None, callbacks={}):
        super(HitBTC, self).__init__('wss://api.hitbtc.com/api/2/ws')
        self.pairs = pairs
        self.channels = channels
        self.book = {}
        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None)}
        for cb in callbacks:
            self.callbacks[cb] = callbacks[cb]

    async def _ticker(self, msg):
        await self.callbacks['ticker'](feed='hitbtc',
                                       pair=pair_exchange_to_std(msg['symbol']),
                                       bid=Decimal(msg['bid']),
                                       ask=Decimal(msg['ask']))

    async def message_handler(self, msg):
        msg = json.loads(msg)
        if 'method' in msg:
            if msg['method'] == 'ticker':
                await self._ticker(msg['params'])
        elif 'channel' in msg:
            if msg['channel'] == 'ticker':
                await self._ticker(msg['data'])
        else:
            try:
                if not msg['result']:
                    print("Received error from server {}".format(msg))
            except:
                print(msg)
                raise
    async def subscribe(self, websocket):
        for channel in self.channels:
            channel = std_channel_to_exchange(channel, 'HITBTC')
            for pair in self.pairs:
                pair = pair_std_to_exchange(pair, 'HITBTC')
                await websocket.send(
                    json.dumps({
                        "method": channel,
                        "params": {
                            "symbol": pair
                        },
                        "id": 123
                    }))
