import json

from feed import Feed


class Poloniex(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(Poloniex, self).__init__('wss://api2.poloniex.com')
        self.channels = channels
        self.pairs = pairs
        self.callbacks = callbacks
        if self.callbacks is None:
            self.callbacks = {'ticker': self._print,
                              'trades': self._print}

    async def message_handler(self, msg):
        msg = json.loads(msg)
        print(msg)

    async def subscribe(self, websocket):
        for channel in self.channels:
            await websocket.send(json.dumps({"command": "subscribe",
                                             "channel": channel
                                            }))