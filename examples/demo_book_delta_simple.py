'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import BOOK_DELTA, L2_BOOK
from cryptofeed.exchanges import Coinbase, Gemini
from datetime import datetime
from cryptofeed.exchange.binance_futures import BinanceFutures


async def abook(feed, pair, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} Snapshot: {book}')


async def delta(feed, pair, delta, timestamp, receipt_timestamp):
    print(f'DELTA lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} Delta: {delta}')


def main():
    f = FeedHandler()
    f.add_feed(BinanceFutures(max_depth=2,
                              pairs=['BTC-USDT'],
                              channels=[L2_BOOK],
                              callbacks={L2_BOOK: abook}))
    # f.add_feed(BinanceFutures(max_depth=2,
    #                     pairs=['BTC-USDT'],
    #                     channels=[L2_BOOK],
    #                     callbacks={BOOK_DELTA: delta,
    #                                L2_BOOK: book}))
    # f.add_feed(Coinbase(max_depth=2,
    #                     pairs=['BTC-USD'],
    #                     channels=[L2_BOOK],
    #                     callbacks={BOOK_DELTA: delta,
    #                                L2_BOOK: book}))
    f.run()


if __name__ == '__main__':
    main()
