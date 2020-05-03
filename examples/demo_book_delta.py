'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from copy import deepcopy

from cryptofeed.callback import BookCallback, BookUpdateCallback
from cryptofeed import FeedHandler
from cryptofeed.exchange.blockchain import Blockchain
from cryptofeed.exchanges import Bitmex, Coinbase, Bitfinex, Gemini, HitBTC, Poloniex, Kraken, OKCoin, Bybit, Binance, Bitstamp, EXX, Bittrex, Upbit
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

    async def handle_book(self, feed, pair, book, timestamp, receipt_timestamp):
        """Handle full book updates."""
        if not self.book:
            self.book = deepcopy(book)
            print("%s: Book Set" % self.name)
        else:
            assert(self.check_books(book))
            print("%s: Books match!" % self.name)

    async def handle_l2_delta(self, feed, pair, update, timestamp, receipt_timestamp):
        """Handle L2 delta updates."""
        # handle updates for L2 books
        for side in (BID, ASK):
            for price, size in update[side]:
                if size == 0:
                    del self.book[side][price]
                else:
                    self.book[side][price] = size

    async def handle_l3_delta(self, feed, pair, update, timestamp, receipt_timestamp):
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
    f.add_feed(Bitmex(max_depth=100, book_interval=1000, pairs=['XBTUSD'], channels=[L2_BOOK], callbacks=DeltaBook("Bitmex").L2))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks=DeltaBook("Bitfinex-L3").L3))
    f.add_feed(Bitfinex(max_depth=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Bitfinex-L2").L2))
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks=DeltaBook("Coinbase-L3").L3))
    f.add_feed(Coinbase(max_depth=50, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Coinbase-L2").L2))
    f.add_feed(EXX(max_depth=25, book_interval=100, pairs=['BTC-USDT'], channels=[L2_BOOK], callbacks=DeltaBook("EXX").L2))
    f.add_feed(Gemini(max_depth=20, book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Gemini").L2))
    f.add_feed(HitBTC(max_depth=10, book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("HitBTC").L2))
    f.add_feed(Poloniex(max_depth=10, book_interval=100, pairs=['BTC-USDT'], channels=[L2_BOOK], callbacks=DeltaBook("Poloniex").L2))
    f.add_feed(Kraken(max_depth=10, book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Kraken").L2))
    f.add_feed(OKCoin(max_depth=100, book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("OKCoin").L2))
    f.add_feed(Bybit(max_depth=100, book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Bybit").L2))
    f.add_feed(Binance(max_depth=100, book_interval=30, pairs=['BTC-USDT'], channels=[L2_BOOK], callbacks=DeltaBook("Binance").L2))
    f.add_feed(Bitstamp(max_depth=100, book_interval=30, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Bitstamp").L2))
    f.add_feed(Bittrex(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Bittrex").L2))
    f.add_feed(Upbit(book_interval=2, pairs=['BTC-KRW'], channels=[L2_BOOK], callbacks=DeltaBook("Upbit").L2))
    f.add_feed(Blockchain(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks=DeltaBook("Blockchain-L2").L2))

    f.run()


if __name__ == '__main__':
    main()
