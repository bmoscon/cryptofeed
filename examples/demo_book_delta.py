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


BOOK = None


def check_books(master, delta):
    """
    check that master is equal to delta
    """
    for side in (BID, ASK):
        if len(master[side]) != len(delta[side]):
            return False

        for price in master[side]:
            if price not in delta[side]:
                return False

        for price in delta[side]:
            if price not in master[side]:
                return False
    return True


async def book(feed, pair, book, timestamp):
    global BOOK
    if not BOOK:
        BOOK = deepcopy(book)
        print("Book Set")
    else:
        assert(check_books(book, BOOK))
        print("Books match!")


async def delta(feed, pair, update, timestamp):
    # handle updates for L2 books
    global BOOK
    for side in (BID, ASK):
        for price, size in update[side]:
            if size == 0:
                del BOOK[side][price]
            else:
                BOOK[side][price] = size


async def l3_delta(feed, pair, update, timestamp):
    global BOOK
    for side in (BID, ASK):
        for order, price, size in update[side]:
            if size == 0:
                del BOOK[side][price][order]
                if len(BOOK[side][price]) == 0:
                    del BOOK[side][price]
            else:
                if price in BOOK[side]:
                    BOOK[side][price][order] = size
                else:
                    BOOK[side][price] = {order: size}


def main():
    f = FeedHandler()
    # due to the way the test verification works, you can only run one for the test
    #f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(l3_delta)}))
    # f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(l3_delta)}))
    # f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    # f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(l3_delta)}))
    # f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    # f.add_feed(Gemini(book_interval=100, pairs=['BTC-USD'], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    # f.add_feed(HitBTC(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    # f.add_feed(Poloniex(book_interval=100, channels=['BTC-USDT'], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    # f.add_feed(Kraken(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    f.add_feed(OKCoin(book_interval=100, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))

    f.run()


if __name__ == '__main__':
    main()
