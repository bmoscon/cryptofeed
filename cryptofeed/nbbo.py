'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.callback import Callback
from cryptofeed.defines import BID, ASK


class NBBO(Callback):
    def __init__(self, callback, pairs):
        self.bids = {pair: {} for pair in pairs}
        self.asks = {pair: {} for pair in pairs}

        self.last_update = None

        super(NBBO, self).__init__(callback)

    def _update(self, feed, pair, book, timestamp):
        bid = Decimal(list(book[BID].keys())[-1])
        size = book[BID][bid]
        self.bids[pair][feed] = {'price': bid, 'size': size}
        ask = Decimal(list(book[ASK].keys())[0])
        size = book[ASK][ask]
        self.asks[pair][feed] = {'price': ask, 'size': size}

        min_ask = min(self.asks[pair], key=lambda x: self.asks[pair][x]['price'])
        max_bid = max(self.bids[pair], key=lambda x: self.bids[pair][x]['price'])

        return self.bids[pair][max_bid], self.asks[pair][min_ask], max_bid, min_ask

    async def __call__(self, *, feed: str, pair: str, book: dict, timestamp):
        update = self._update(feed, pair, book, timestamp)

        # only write updates when a best bid / best aks changes
        if self.last_update == update:
            return
        self.last_update = update

        bid, ask, bid_feed, ask_feed = update
        if bid is None:
            return
        if self.is_async:
            await self.callback(pair, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, pair, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
