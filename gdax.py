import json

from feed import Feed


class GDAX(Feed):
    def __init__(self, pairs=None, channels=None):
        super(GDAX, self).__init__('wss://ws-feed.gdax.com')
        self.channels = channels
        self.pairs = pairs
    
    def message_handler(self, msg):
        msg = json.loads(msg)
        print(msg)
    
    async def subscribe(self, websocket):
        websocket.send(json.dumps({"type": "subscribe",
                                   "product_ids": self.pairs,
                                   "channels": self.channels
                                }))
