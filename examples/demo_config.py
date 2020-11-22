'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L3_BOOK, TRADES
from cryptofeed.exchanges import Coinbase


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp, order_type):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price} Order Type {order_type}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(config={TRADES: ['BTC-USD'], L3_BOOK: ['ETH-USD']}, callbacks={TRADES: TradeCallback(trade, include_order_type=True), L3_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
