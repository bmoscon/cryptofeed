'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, TRADES
from cryptofeed.exchanges import HuobiSwap


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    fh = FeedHandler()

    callbacks = {TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}
    fh.add_feed(HuobiSwap(pairs=['BTC-USD'], channels=[TRADES, L2_BOOK], callbacks=callbacks))

    fh.run()


if __name__ == '__main__':
    main()
