'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, TRADES
from cryptofeed.exchanges import Bybit


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    f = FeedHandler()

    f.add_feed(Bybit(pairs=['BTC-USD', 'ETH-USD', 'XRP-USD', 'EOS-USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Bybit(pairs=['BTC-USD', 'ETH-USD', 'XRP-USD', 'EOS-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
