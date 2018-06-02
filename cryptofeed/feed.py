'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from time import time
from datetime import datetime, timezone

from cryptofeed.callback import Callback
from cryptofeed.standards import pair_std_to_exchange
from cryptofeed.feeds import TRADES, TICKER, L2_BOOK, L3_BOOK, L3_BOOK_UPDATE, VOLUME, feed_to_exchange


class Feed:
    id = 'NotImplemented'

    # default_interval in seconds
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

        self.intervals = defaultdict(lambda: default_interval)  # {func_name: schedule_interval_in_seconds}
        if intervals is not None:
            self.intervals.update(intervals)

        if callbacks:
            for cb in callbacks:
                self.callbacks[cb] = callbacks[cb]

    @staticmethod
    def tz_aware_datetime_from_string(tstring: str) -> datetime:
        """
        from ISO compliant string to tz aware datetime object
        :param tstring: timestamp string
        :return: tz aware datetime object
        """
        # test for UNIX timestamp first
        try:
            timestamp = datetime.fromtimestamp(float(tstring), tz=timezone.utc)

        # assume ISO timestamp
        except ValueError:
            try:
                # test for `Z` (Zulu time) instead of offset UTC +0000
                timestamp = datetime.strptime(tstring, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
            except ValueError:
                timestamp = datetime.strptime(tstring, '%Y-%m-%dT%H:%M:%S.%f%z')
        return timestamp

    async def synthesize_feed(self, func, *args, **kwargs):
        interval = self.intervals[func.__name__]
        start_time = time()
        while True:
            message = await func(*args, **kwargs)
            asyncio.ensure_future(self.message_handler(message))
            await asyncio.sleep(
                interval - ((time() - start_time) % interval)
            )

    async def message_handler(self, msg):
        raise NotImplementedError
