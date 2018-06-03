from time import time
import asyncio
import json

import requests

from cryptofeed.exchanges import GDAX
from cryptofeed.defines import TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.feedhandler import FeedHandler


def test_periodic_snapshots_with_gdax_channels():

    class TestFeed(Feed):
        id = GDAX

        def __init__(self, pairs=None, channels=None, num_calls=20, intervals=None):
            intervals = intervals or {'test': .5}
            super().__init__('wss://ws-feed.gdax.com', pairs=pairs, channels=channels, intervals=intervals)
            self.call_times = []
            self.num_calls = num_calls

        async def test(self):
            self.call_times.append(time())
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, requests.get, 'http://httpbin.org/get')
            if len(self.call_times) == self.num_calls:
                try:
                    for idx in range(len(self.call_times) - 1):
                        high_range = self.intervals['test'] + .01
                        low_range = self.intervals['test'] - .01
                        delay = self.call_times[idx+1] - self.call_times[idx]
                        assert low_range <= delay <= high_range, \
                            'Delay between calls {} is greater than the specified interval {}.'.format(
                                delay,
                                self.intervals['test']
                            )
                finally:
                    loop.call_soon(loop.stop)

        async def message_handler(self, msg):
            return msg

        async def subscribe(self, websocket):
            await websocket.send(json.dumps({"type": "subscribe",
                                             "product_ids": self.pairs,
                                             "channels": self.channels
                                             }))
            asyncio.ensure_future(self.synthesize_feed(self.test))

    f = FeedHandler()

    f.add_feed(TestFeed(pairs=['BTC-USD', 'ETH-BTC', 'LTC-BTC'],
                        channels=[TICKER, TRADES],
                        intervals={'test': .5},
                        num_calls=10))
    f.run()
