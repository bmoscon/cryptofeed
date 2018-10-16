'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange
from cryptofeed.feeds import feed_to_exchange
from cryptofeed.defines import TRADES, TICKER, L2_BOOK, L3_BOOK, VOLUME, FUNDING, BOOK_DELTA
from cryptofeed.callback import BookUpdateCallback
from cryptofeed.exchanges import BITFINEX


class Feed:
    id = 'NotImplemented'

    def __init__(self, address, pairs=None, channels=None, callbacks=None, book_interval=1000):
        self.address = address
        self.standardized_pairs = pairs
        self.standardized_channels = channels
        self.book_update_interval = book_interval
        self.updates = 0
        self.do_deltas = False

        if channels is not None and FUNDING in channels and self.id == BITFINEX:
            if len(channels) > 1:
                raise ValueError("Funding channel must be in a separate feedhanlder on Bitfinex")

        if pairs:
            self.pairs = [pair_std_to_exchange(pair, self.id) for pair in pairs]
        if channels:
            self.channels = [feed_to_exchange(self.id, chan) for chan in channels]

        self.l3_book = {}
        self.l2_book = {}
        self.callbacks = {TRADES: Callback(None),
                          TICKER: Callback(None),
                          L2_BOOK: Callback(None),
                          L3_BOOK: Callback(None),
                          VOLUME: Callback(None),
                          FUNDING: Callback(None)}


        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]
                if isinstance(callbacks[cb], BookUpdateCallback):
                    self.do_deltas = True

    async def book_callback(self, pair, book_type, forced, delta, timestamp):
        if self.do_deltas and self.updates < self.book_update_interval and not forced:
            self.updates += 1
            await self.callbacks[BOOK_DELTA](feed=self.id, pair=pair, delta=delta, timestamp=timestamp)

        if self.updates >= self.book_update_interval or forced or not self.do_deltas:
            self.updates = 0
            if book_type == L2_BOOK:
                await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair], timestamp=timestamp)
            else:
                await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l3_book[pair], timestamp=timestamp)

    def message_handler(self, msg):
        raise NotImplementedError


class RestFeed(Feed):
    pass
