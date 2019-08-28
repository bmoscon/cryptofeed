'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import OKEx
from cryptofeed.defines import L2_BOOK_SWAP, L2_BOOK, BID, ASK, TRADES, TRADES_SWAP




async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    fh = FeedHandler()

    fh.add_feed(OKEx(pairs=['EOS-USD-SWAP'], channels=[TRADES_SWAP, L2_BOOK_SWAP], callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    fh.run()


if __name__ == '__main__':
    main()
