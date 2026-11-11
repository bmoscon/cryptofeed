'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback


class NBBO(Callback):
    def __init__(self, callback, symbols):
        self.bids = {symbol: {} for symbol in symbols}
        self.asks = {symbol: {} for symbol in symbols}

        self.last_update = {}

        super(NBBO, self).__init__(callback)

    def _update(self, book):
        for side, quotes in ((book.book.bids, self.bids[book.symbol]),
                             (book.book.asks, self.asks[book.symbol])):
            if len(side):
                price, size = side.index(0)
                quotes[book.exchange] = {'price': price, 'size': size}
            else:
                quotes.pop(book.exchange, None)

        if not self.bids[book.symbol] or not self.asks[book.symbol]:
            return None

        min_ask = min(self.asks[book.symbol], key=lambda x: self.asks[book.symbol][x]['price'])
        max_bid = max(self.bids[book.symbol], key=lambda x: self.bids[book.symbol][x]['price'])

        return self.bids[book.symbol][max_bid], self.asks[book.symbol][min_ask], max_bid, min_ask

    async def __call__(self, book, receipt_timestamp: float):
        update = self._update(book)
        if update is None:
            return

        # only write updates when a best bid / best ask changes
        if self.last_update.get(book.symbol) == update:
            return
        self.last_update[book.symbol] = update

        bid, ask, bid_feed, ask_feed = update
        await self.callback(book.symbol, bid['price'], bid['size'], ask['price'], ask['size'], bid_feed, ask_feed)
