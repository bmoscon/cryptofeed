'''
Copyright (C) 2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from copy import deepcopy

from cryptofeed.callback import BookCallback, BookUpdateCallback
from cryptofeed import FeedHandler
from cryptofeed import Bitmex, GDAX
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, UPD, ADD, DEL, BOOK_DELTA


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


async def book(feed, pair, book):
    global BOOK
    if not BOOK:
        BOOK = deepcopy(book)
        print("Book Set")
    else:
        assert(check_books(book, BOOK))
        print("Books match!")


async def delta(feed, pair, update):
    global BOOK
    for side in (BID, ASK):
        for price, size in update[side][ADD]:
            BOOK[side][price] = size
        for price, size in update[side][UPD]:
            BOOK[side][price] = size
        for price in update[side][DEL]:
            del BOOK[side][price]


def main():
    f = FeedHandler()
    # due to the way the test verification works, you can only run one or the other for this test
    #f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    f.add_feed(GDAX(pairs=['BTC-USD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book), BOOK_DELTA: BookUpdateCallback(delta)}))
    f.run()


if __name__ == '__main__':
    main()
