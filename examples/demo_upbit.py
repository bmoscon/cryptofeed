from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, TRADES
from cryptofeed.exchanges import Upbit


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    upbit_active_pairs = Upbit.get_active_symbols()

    f = FeedHandler()
    f.add_feed(Upbit(pairs=upbit_active_pairs, channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Upbit(pairs=upbit_active_pairs, channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
