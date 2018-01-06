'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed.callback import Callback


class NBBO(Callback):
    def __init__(self, callback, pair):
        self.bids = {}
        self.asks = {}
        self.pair = pair
        super(NBBO, self).__init__(callback)

    async def _update(self, feed, pair, bid, ask):
        if pair != self.pair:
            return None, None, None, None
        self.bids[feed] = bid
        self.asks[feed] = ask

        min_ask = min(self.bids, key=self.bids.get)
        max_bid = max(self.asks, key=self.asks.get)

        return self.bids[max_bid], self.asks[min_ask], max_bid, min_ask

    async def __call__(self, *, feed: str, pair: str, bid:  float, ask: float):
        bid, ask, bid_feed, ask_feed = await self._update(feed, pair, bid, ask)
        if bid is None:
            return
        if self.is_async:
            await self.callback(pair, bid, ask, bid_feed, ask_feed)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, pair, bid, ask, bid_feed, ask_feed)
