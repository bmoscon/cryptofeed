from decimal import Decimal
from datetime import datetime
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, FundingCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, COINBASE, FUNDING, GEMINI, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, VOLUME
from cryptofeed.exchanges import BinanceDelivery
import logging
logging.basicConfig(level='DEBUG')
data_info = BinanceDelivery.info()

DEPTH = 20

def book2msg(dict_book, depth=DEPTH):
    l_bid = ["bid{i}={v1},bsize{i}={v2}".format(i=depth - i, v1=k[0], v2=k[1]) for i, k in enumerate(dict_book['bid'].items())]
    l_ask = ["ask{i}={v1},asize{i}={v2}".format(i=i, v1=k[0], v2=k[1]) for i, k in enumerate(dict_book['ask'].items())]
    return ','.join(l_bid+l_ask)



async def abook(feed, pair, book, timestamp, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} '
          f'Snapshot: {book2msg(book)}')


async def delta(feed, pair, delta, timestamp, receipt_timestamp):
    print(f'DELTA lag: {receipt_timestamp - timestamp} Timestamp: {datetime.fromtimestamp(timestamp)} '
          f'Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)} Feed: {feed} Pair: {pair} Delta: {delta}')



def main():
    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=DEPTH,
                              pairs=['BTC-USD_PERP'],
                              channels=[L2_BOOK],
                              callbacks={L2_BOOK: abook}))
    f.run()


if __name__ == '__main__':
    main()