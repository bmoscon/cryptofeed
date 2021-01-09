from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchanges import BinanceDelivery

data_info = BinanceDelivery.info()


async def abook(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def delta(feed, symbol, delta, timestamp, receipt_timestamp):
    print(f'DELTA lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Delta: {delta}')


def main():
    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=3,
                               symbols=['BTC-USD_201225'],
                               channels=[L2_BOOK],
                               callbacks={L2_BOOK: abook}))
    f.run()


if __name__ == '__main__':
    main()
