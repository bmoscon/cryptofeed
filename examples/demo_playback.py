'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

from cryptofeed import FeedHandler
from cryptofeed.defines import L3_BOOK, TRADES, TICKER, BID, ASK
from cryptofeed.exchanges import Coinbase


async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price, order_type, receipt_timestamp):
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    demo_dir = os.path.dirname(os.path.realpath(__file__))
    f = FeedHandler()
    feed = Coinbase(pairs=['BTC-USD'], callbacks={L3_BOOK: book, TICKER: ticker, TRADES: trade})

    stats = f.playback(feed, os.path.join(demo_dir, 'COINBASE-7e24b862-b42c-4fd8-a99e-4791a3ff84a5.0'))

    print("\nPlayback complete!")
    print(stats)

if __name__ == '__main__':
    main()
