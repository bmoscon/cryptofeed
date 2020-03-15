#import sys
#sys.path.insert(0, '../')
from cryptofeed.callback import TradeCallback, BookCallback
from cryptofeed import FeedHandler

from cryptofeed.exchanges import Bybit, Upbit
from cryptofeed.defines import TRADES, L2_BOOK, BID, ASK


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    f = FeedHandler()

    f.add_feed(Upbit(pairs=['BTC-KRW', 'ETH-KRW', 'XRP-KRW', 'EOS-KRW'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    #f.add_feed(Upbit(pairs=['BTC-KRW', 'ETH-KRW', 'XRP-KRW', 'EOS-KRW'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
