from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import BinanceDelivery


info = BinanceDelivery.info()


async def abook(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {symbol} Snapshot: {book}')


async def ticker(**kwargs):
    print(kwargs)


async def trades(**kwargs):
    print(kwargs)


def main():
    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=3, symbols=[info['symbols'][-1]],
                               channels=[L2_BOOK, TRADES, TICKER],
                               callbacks={L2_BOOK: abook, TRADES: trades, TICKER: ticker}))
    f.run()


if __name__ == '__main__':
    main()
