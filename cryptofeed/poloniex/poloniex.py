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
    async def _ticker(self, msg):
        print(msg)
    
    async def _volume(self, msg):
        print(msg)

    async def message_handler(self, msg):
        msg = json.loads(msg)
        chan_id = msg[0]

        if chan_id == 1002:
            '''
            the ticker channel doesn't have sequence ids
            so it should be None, except for the subscription
            ack, in which case its 1
            '''
            seq_id = msg[1]
            if seq_id is None:
                await self._ticker(msg[2])
        elif chan_id == 1003:
            '''
            volume update channel is just like ticker - the 
            sequence id is None except for the initial ack
            '''
            seq_id = msg[1]
            if seq_id is None:
                await self._volume(msg[2])
        
        elif chan_id == 1010:
            #heartbeat - ignore
            pass
        else:
            print('Invalid message type {}'.format(msg))

    async def subscribe(self, websocket):
        for channel in self.channels:
            await websocket.send(json.dumps({"command": "subscribe",
                                             "channel": channel
                                            }))