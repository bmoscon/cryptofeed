'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from copy import deepcopy

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchanges import Coinbase


PREV = {}
counter = 0


async def book(feed, symbol, book, timestamp):
    global PREV
    global counter
    if book == PREV:
        print("Current")
        print(book)
        print("\n\n")
        print("Previous")
        print(PREV)
    assert book != PREV
    PREV = deepcopy(book)
    counter += 1
    if counter % 10 == 0:
        print(".", end='', flush=True)


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(max_depth=5, symbols=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.run()


if __name__ == '__main__':
    main()
