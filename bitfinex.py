import json

from feed import Feed


class Bitfinex(Feed):
    def __init__(self, pairs=None, channels=None):
        super(Bitfinex, self).__init__('wss://api.bitfinex.com/ws/2')
        self.pairs = pairs
        self.channels = channels
        self.channel_map = {}
    
    def _ticker(self, msg):
        chan_id = msg[0]
        if msg[1] == 'hb':
            pass
        else:
            bid, bid_size, ask, ask_size, \
            daily_change, daily_change_perc, \
            last_price, volume, high, low = msg[1]
            pair = self.channel_map[chan_id]['symbol']
            channel = self.channel_map[chan_id]['channel']
            print("Channel: {} Pair: {} Bid: {} Ask: {}".format(channel, pair, bid, ask))
    
    def _trades(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        def _trade_msg(trade):
            trade_id, timestamp, amount, price = trade
            if amount < 0:
                side = 'SELL'
            else:
                side = 'BUY'
            amount = abs(amount)
            channel = self.channel_map[chan_id]['channel']
            print('Channel: {} Pair: {} Side: {} Amount: {} Price: {}'.format(channel, pair, side, amount, price))
        
        if isinstance(msg[1], list):
            # snapshot
            for trade_update in msg[1]:
                _trade_msg(trade_update)
        else:
            # update
            if msg[1] == 'te':
                _trade_msg(msg[2])
            elif msg[1] == 'tu':
                # ignore trade updates
                pass
            elif msg[1] == 'hb':
                # ignore heartbeats
                pass
            else:
                print("Unexpected trade message {}".format(msg))

    def message_handler(self, msg):
        msg = json.loads(msg)
        if isinstance(msg, list):
            chan_id = msg[0]
            if chan_id in self.channel_map:
                self.channel_map[chan_id]['handler'](msg)
            else:
               print("Unexpected message on unregistered channel {}".format(msg))

        elif 'chanId' in msg and 'symbol' in msg:
            handler = None
            if msg['channel'] == 'ticker':
                handler = self._ticker
            elif msg['channel'] == 'trades':
                handler = self._trades
            elif msg['channel'] == 'book':
                if msg['prec'] == 'R0':
                    handler = self._raw_book
                else:
                    handler = self._book
            else:
                print('Invalid message type {}'.format(msg))
            self.channel_map[msg['chanId']] = {'symbol': msg['symbol'], 
                                               'channel': msg['channel'],
                                               'handler': handler}


    async def subscribe(self, websocket):
        for channel in self.channels:
            for pair in self.pairs:
                await websocket.send(json.dumps({'event': 'subscribe',
                                'channel': channel,
                                'symbol': pair
                                }))