'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import BOOK_DELTA, L2_BOOK
from cryptofeed.exchanges import Coinbase


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Receipt Timestamp: {receipt_timestamp} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def delta(feed, symbol, delta, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Receipt Timestamp: {receipt_timestamp} Feed: {feed} Pair: {symbol} Delta: {delta}')


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(max_depth=2, symbols=['BTC-USD'], channels=[L2_BOOK], callbacks={BOOK_DELTA: delta, L2_BOOK: book}))

    f.run()


if __name__ == '__main__':
    main()
