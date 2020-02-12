'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import uuid
from collections import defaultdict

from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange, feed_to_exchange, load_exchange_pair_mapping
from cryptofeed.defines import TRADES, TICKER, L2_BOOK, L3_BOOK, VOLUME, FUNDING, BOOK_DELTA, OPEN_INTEREST, BID, ASK
from cryptofeed.util.book import book_delta, depth


class Feed:
    id = 'NotImplemented'

    def __init__(self, address, pairs=None, channels=None, config=None, callbacks=None, max_depth=None, book_interval=1000):
        self.hash = str(uuid.uuid4())
        self.uuid = self.id + self.hash
        self.config = defaultdict(set)
        self.address = address
        self.book_update_interval = book_interval
        self.updates = defaultdict(int)
        self.do_deltas = False
        self.pairs = []
        self.channels = []
        self.max_depth = max_depth
        self.previous_book = defaultdict(dict)
        load_exchange_pair_mapping(self.id)

        if config is not None and (pairs is not None or channels is not None):
            raise ValueError("Use config, or channels and pairs, not both")

        if config is not None:
            for channel in config:
                chan = feed_to_exchange(self.id, channel)
                self.config[chan].update([pair_std_to_exchange(pair, self.id) for pair in config[channel]])

        if pairs:
            self.pairs = [pair_std_to_exchange(pair, self.id) for pair in pairs]
        if channels:
            self.channels = list(set([feed_to_exchange(self.id, chan) for chan in channels]))

        self.l3_book = {}
        self.l2_book = {}
        self.callbacks = {TRADES: Callback(None),
                          TICKER: Callback(None),
                          L2_BOOK: Callback(None),
                          L3_BOOK: Callback(None),
                          VOLUME: Callback(None),
                          FUNDING: Callback(None),
                          OPEN_INTEREST: Callback(None)}

        if callbacks:
            for cb_type, cb_func in callbacks.items():
                self.callbacks[cb_type] = cb_func
                if cb_type == BOOK_DELTA:
                    self.do_deltas = True

        for key, callback in self.callbacks.items():
            if not isinstance(callback, list):
                self.callbacks[key] = [callback]

    async def book_callback(self, book, book_type, pair, forced, delta, timestamp):
        """
        Three cases we need to handle here

        1.  Book deltas are enabled (application of max depth here is trivial)
        1a. Book deltas are enabled, max depth is not, and exchange does not support deltas. Rare
        2.  Book deltas not enabled, but max depth is enabled
        3.  Neither deltas nor max depth enabled

        2 and 3 can be combined into a single block as long as application of depth modification
        happens first

        For 1, need to handle separate cases where a full book is returned vs a delta
        """
        if self.do_deltas:
            if not forced and self.updates[pair] < self.book_update_interval:
                if self.max_depth:
                    delta, book = await self.apply_depth(book, True, pair)
                    if not (delta[BID] or delta[ASK]):
                        return
                elif not delta:
                    # this will only happen in cases where an exchange does not support deltas and max depth is not enabled.
                    # this is an uncommon situation. Exchanges that do not support deltas will need
                    # to populate self.previous internally to avoid the unncesessary book copy on all other exchanges
                    delta = book_delta(self.previous_book[pair], book, book_type=book_type)
                    if not (delta[BID] or delta[ASK]):
                        return
                self.updates[pair] += 1
                await self.callback(BOOK_DELTA, feed=self.id, pair=pair, delta=delta, timestamp=timestamp)
                if self.updates[pair] != self.book_update_interval:
                    return
            elif forced and self.max_depth:
                # We want to send a full book update but need to apply max depth first
                _, book = await self.apply_depth(book, False, pair)
        elif self.max_depth:
            changed, book = await self.apply_depth(book, False, pair)
            if not changed:
                return
        if book_type == L2_BOOK:
            await self.callback(L2_BOOK, feed=self.id, pair=pair, book=book, timestamp=timestamp)
        else:
            await self.callback(L3_BOOK, feed=self.id, pair=pair, book=book, timestamp=timestamp)
        self.updates[pair] = 0

    async def callback(self, data_type, **kwargs):
        for cb in self.callbacks[data_type]:
            await cb(**kwargs)

    async def apply_depth(self, book: dict, do_delta: bool, pair: str):
        ret = depth(book, self.max_depth)
        if not do_delta:
            delta = self.previous_book[pair] != ret
            self.previous_book[pair] = ret
            return delta, ret

        delta = []
        delta = book_delta(self.previous_book[pair], ret)
        self.previous_book[pair] = ret
        return delta, ret

    async def message_handler(self, msg: str, timestamp: float):
        raise NotImplementedError


class RestFeed(Feed):
    async def message_handler(self):
        raise NotImplementedError
