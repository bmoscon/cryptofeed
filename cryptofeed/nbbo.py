'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.callback import Callback
from cryptofeed.defines import BID, ASK


class NBBO(Callback):
    def __init__(self, callback, symbols):
        self.bids = {symbol: {} for symbol in symbols}
        self.asks = {symbol: {} for symbol in symbols}

        self.last_update = None

        super(NBBO, self).__init__(callback)

    def _update(self, feed, symbol, book):
        bid = Decimal(list(book[BID].keys())[-1])
        size = book[BID][bid]
        self.bids[symbol][feed] = {'price': bid, 'size': size}
        ask = Decimal(list(book[ASK].keys())[0])
        size = book[ASK][ask]
        self.asks[symbol][feed] = {'price': ask, 'size': size}

        min_ask = min(self.asks[symbol], key=lambda x: self.asks[symbol][x]['price'])
        max_bid = max(self.bids[symbol], key=lambda x: self.bids[symbol][x]['price'])

        return self.bids[symbol][max_bid], self.asks[symbol][min_ask], max_bid, min_ask

    async def __call__(self, *, feed: str, symbol: str, book: dict, timestamp: float, receipt_timestamp: float):
        update = self._update(feed, symbol, book)

        # only write updates when a best bid / best aks changes
        if self.last_update == update:
            return
        self.last_update = update

        bid, ask, bid_feed, ask_feed = update
        if bid is None:
            return
        if self.is_async:
            await self.callback(symbol, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, symbol, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
