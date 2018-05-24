'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from time import time
import json

from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange
from cryptofeed.utils import call_periodically
from cryptofeed.feeds import TRADES, TICKER, L2_BOOK, L3_BOOK, L3_BOOK_UPDATE, VOLUME, feed_to_exchange


class Feed:
    id = 'NotImplemented'

    # default_interval == 1 hour
    def __init__(self, address: str, pairs=None, channels=None, callbacks=None, intervals=None, default_interval=60*60):
        self.address = address
        self.standardized_pairs = pairs
        self.standardized_channels = channels

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
                          L3_BOOK_UPDATE: Callback(None),
                          VOLUME: Callback(None)}

        assert isinstance(intervals, dict) or intervals is None, \
            f'`intervals` arg must be of type dict or None, got {intervals.__class__.__name__} instead'
        self.intervals = defaultdict(lambda: default_interval)  # {func_name: schedule_interval_in_seconds}
        if intervals is not None:
            self.intervals.update(intervals)

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    async def synthesize_feed(self, func, *args, **kwargs):
        interval = self.intervals[func.__name__]
        start_time = time()
        while True:
            print('synthesizing')
            message = func(*args, **kwargs)
            print(f'Synthesized msg type: {json.loads(message)["type"]}')
            asyncio.ensure_future(self.message_handler(message))
            await asyncio.sleep(
                interval - ((time() - start_time) % interval)
            )
        # asyncio.ensure_future(call_periodically(self.intervals[func.__name__], func, *args, callback=self.message_handler, **kwargs))

    async def message_handler(self, msg):
        raise NotImplementedError
