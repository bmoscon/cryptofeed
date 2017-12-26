import json

from feed import Feed


class GDAX(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(GDAX, self).__init__('wss://ws-feed.gdax.com')
        self.channels = channels
        self.pairs = pairs
        self.callbacks = callbacks
        if self.callbacks is None:
            self.callbacks = {'ticker': self._print}
    
    async def _ticker(self, msg):
        self.callbacks['ticker']({'feed': 'gdax',
                                  'channel': 'ticker',
                                  'pair': msg['product_id'],
                                  'bid': msg['best_bid'],
                                  'ask': msg['best_ask']})
    
    async def message_handler(self, msg):
        msg = json.loads(msg)
        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg)
    
    async def subscribe(self, websocket):
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
