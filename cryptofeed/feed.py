'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange
from cryptofeed.feeds import TRADES, TICKER, L2_BOOK, L3_BOOK, feed_to_exchange
class Feed(object):
    id = 'NotImplemented'

    def __init__(self, address, pairs=None, channels=None, callbacks=None):
        self.address = address
        self.pairs = [pair_std_to_exchange(pair, self.id) for pair in pairs]
        self.channels = [feed_to_exchange(self.id, chan) for chan in channels]
        self.book = {}
        self.callbacks = {TRADES: Callback(None),
                          TICKER: Callback(None),
                          L2_BOOK: Callback(None),
                          L3_BOOK: Callback(None)}

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    def message_handler(self, msg):
        raise NotImplementedError
