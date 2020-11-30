from decimal import Decimal
from datetime import datetime
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, FundingCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, COINBASE, FUNDING, GEMINI, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, VOLUME
from cryptofeed.exchanges import BinanceDelivery

data_info = BinanceDelivery.info()


async def abook(feed, pair, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} Snapshot: {book}')


async def delta(feed, pair, delta, timestamp, receipt_timestamp):
    print(f'DELTA lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} Delta: {delta}')


def main():
    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=3,
                              pairs=['BTC-USD_201225'],
                              channels=[L2_BOOK],
                              callbacks={L2_BOOK: abook}))
    f.run()


if __name__ == '__main__':
    main()