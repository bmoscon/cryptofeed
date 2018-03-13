'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.callback import Callback


class NBBO(Callback):
    def __init__(self, callback, pairs):
        self.bids = {pair: {} for pair in pairs}
        self.asks = {pair: {} for pair in pairs}
        super(NBBO, self).__init__(callback)

    async def _update(self, feed, pair, bid, ask):
        self.bids[pair][feed] = bid
        self.asks[pair][feed] = ask

        min_ask = min(self.bids[pair], key=self.bids[pair].get)
        max_bid = max(self.asks[pair], key=self.asks[pair].get)

        return self.bids[pair][max_bid], self.asks[pair][min_ask], max_bid, min_ask

    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal):
        bid, ask, bid_feed, ask_feed = await self._update(feed, pair, bid, ask)
        if bid is None:
            return
        if self.is_async:
            await self.callback(pair, bid, ask, bid_feed, ask_feed)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, pair, bid, ask, bid_feed, ask_feed)
