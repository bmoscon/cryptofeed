'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback


class Bitstamp(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(Bitstamp, self).__init__('wss://ws.pusherapp.com/app/de504dc5763aeef9ff52?protocol=7&client=js&version=2.1.6&flash=false')
        self.channels = channels
        self.pairs = pairs
        self.book = {}
        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None)}
        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def message_handler(self, msg):
        print(msg)

    async def subscribe(self, websocket):
        await websocket.send(json.dumps(
            {
                "event": "pusher:subscribe",
		        "data": {
			        "channel": "live_trades"
                }
		    }
        )) 