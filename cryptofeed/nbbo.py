'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed.callback import Callback


class NBBO(Callback):
    def __init__(self, callback, symbols):
        self.bids = {symbol: {} for symbol in symbols}
        self.asks = {symbol: {} for symbol in symbols}

        self.last_update = None

        super(NBBO, self).__init__(callback)

    def _update(self, book):
        bid, size = book.book.bids.index(0)
        self.bids[book.symbol][book.exchange] = {'price': bid, 'size': size}
        ask, size = book.book.asks.index(0)
        self.asks[book.symbol][book.exchange] = {'price': ask, 'size': size}

        min_ask = min(self.asks[book.symbol], key=lambda x: self.asks[book.symbol][x]['price'])
        max_bid = max(self.bids[book.symbol], key=lambda x: self.bids[book.symbol][x]['price'])

        return self.bids[book.symbol][max_bid], self.asks[book.symbol][min_ask], max_bid, min_ask

    async def __call__(self, book, receipt_timestamp: float):
        update = self._update(book)

        # only write updates when a best bid / best aks changes
        if self.last_update == update:
            return
        self.last_update = update

        bid, ask, bid_feed, ask_feed = update
        if bid is None:
            return
        if self.is_async:
            await self.callback(book.symbol, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, book.symbol, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
