import json

from feed import Feed


class GDAX(Feed):
    def __init__(self, pairs=None, channels=None, callbacks=None):
        super(GDAX, self).__init__('wss://ws-feed.gdax.com')
        self.channels = channels
        self.pairs = pairs
        self.callbacks = callbacks
        if self.callbacks is None:
            self.callbacks = {'ticker': self._print,
                              'trades': self._print}
    
    async def _ticker(self, msg):
        self.callbacks['ticker']({'feed': 'gdax',
                                  'channel': 'ticker',
                                  'pair': msg['product_id'],
                                  'bid': msg['best_bid'],
                                  'ask': msg['best_ask']})
    
    async def _trades(self, msg):
        # GDAX calls this 'match'
    
    async def message_handler(self, msg):
        msg = json.loads(msg)
        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg)
            elif msg['type'] == 'match':
                await self._trades(msg)
    
    async def subscribe(self, websocket):
        await websocket.send(json.dumps({"type": "subscribe",
                                         "product_ids": self.pairs,
                                         "channels": self.channels
                                        }))
