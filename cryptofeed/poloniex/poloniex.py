'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from .pairs import poloniex_id_pair_mapping

class Poloniex(Feed):
    def __init__(self, pairs=None, channels=None, callbacks={}):
        super(Poloniex, self).__init__('wss://api2.poloniex.com')
        self.channels = channels
        if pairs:
            raise ValueError("Poloniex does not support pairs on a channel")
        
        self.callbacks = {'trades': Callback(None),
                          'ticker': Callback(None),
                          'book': Callback(None),
                          'volume': Callback(None)}
        
        for cb in callbacks:
            self.callbacks[cb] = callbacks[cb]

    async def _ticker(self, msg):
        # currencyPair, last, lowestAsk, highestBid, percentChange, baseVolume,
        # quoteVolume, isFrozen, 24hrHigh, 24hrLow
        pair_id, _, ask, bid, _, _, _, _, _, _ = msg
        pair = poloniex_id_pair_mapping[pair_id] 
        await self.callbacks['ticker'](feed='poloniex', 
                                       pair=pair,
                                       bid=Decimal(bid),
                                       ask=Decimal(ask))
    
    async def _volume(self, msg):
        # ['2018-01-02 00:45', 35361, {'BTC': '43811.201', 'ETH': '6747.243', 'XMR': '781.716', 'USDT': '196758644.806'}]
        # timestamp, exchange volume, dict of top volumes
        _, _, top_vols = msg
        for pair in top_vols:
            top_vols[pair] = Decimal(top_vols[pair])
        self.callbacks['volume'](feed='poloniex', **top_vols)
    
    async def _book(self, msg):
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
        elif chan_id <= 200:
            '''
            order book updates - the channel id refers to 
            the trading pair being updated
            '''
            await self._book(msg)
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