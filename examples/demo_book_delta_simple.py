'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import L2_BOOK, BOOK_DELTA


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Snapshot: {book}')


async def delta(feed, pair, delta, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Delta: {delta}')


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(max_depth=2, pairs=['BTC-USD'], channels=[L2_BOOK], callbacks={BOOK_DELTA: delta, L2_BOOK: book}))

    f.run()


if __name__ == '__main__':
    main()
