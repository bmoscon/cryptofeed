'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from copy import deepcopy

from cryptofeed.callback import BookCallback, BookUpdateCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Coinbase, Bitfinex, Gemini, HitBTC, Poloniex, Kraken, OKCoin
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, BOOK_DELTA


class DeltaBook(object):
    def __init__(self, name):
        self.book = None
        self.name = name
        self.L2 = {L2_BOOK: BookCallback(self.handle_book),
                   BOOK_DELTA: BookUpdateCallback(self.handle_l2_delta)}
        self.L3 = {L3_BOOK: BookCallback(self.handle_book),
                   BOOK_DELTA: BookUpdateCallback(self.handle_l3_delta)}

    def check_books(self, master):
        """Check that master is equal to self.book."""
        for side in (BID, ASK):
            if len(master[side]) != len(self.book[side]):
                return False

            for price in master[side]:
                if price not in self.book[side]:
                    return False

            for price in self.book[side]:
                if price not in master[side]:
                    return False
        return True

    async def handle_book(self, feed, pair, book, timestamp):
        """Handle full book updates."""
        if not self.book:
            self.book = deepcopy(book)
            print("%s: Book Set" % self.name)
        else:
            assert(self.check_books(book))
            print("%s: Books match!" % self.name)

    async def handle_l2_delta(self, feed, pair, update, timestamp):
        """Handle L2 delta updates."""
        # handle updates for L2 books
        for side in (BID, ASK):
            for price, size in update[side]:
                if size == 0:
                    del self.book[side][price]
                else:
                    self.book[side][price] = size

    async def handle_l3_delta(self, feed, pair, update, timestamp):
        """Handle L3 delta updates."""
        for side in (BID, ASK):
            for order, price, size in update[side]:
                if size == 0:
                    del self.book[side][price][order]
                    if len(self.book[side][price]) == 0:
                        del self.book[side][price]
                else:
                    if price in self.book[side]:
                        self.book[side][price][order] = size
                    else:
                        self.book[side][price] = {order: size}


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L3_BOOK], callbacks=DeltaBook("Bitmex").L3))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks=DeltaBook("Bitfinex-L3").L3))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Bitfinex-L2").L2))
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks=DeltaBook("Coinbase-L3").L3))
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Coinbase-L2").L2))
    f.add_feed(Gemini(book_interval=100, pairs=['BTC-USD'], callbacks=DeltaBook("Gemini").L2))
    f.add_feed(HitBTC(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("HitBTC").L2))
    f.add_feed(Poloniex(book_interval=100, channels=['BTC-USDT'], callbacks=DeltaBook("Poloniex").L2))
    f.add_feed(Kraken(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Kraken").L2))
    f.add_feed(OKCoin(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("OKCoin").L2))
    f.run()


if __name__ == '__main__':
    main()
