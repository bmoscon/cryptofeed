'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import logging

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback
from cryptofeed.defines import L2_BOOK, BID, ASK, BLOCKCHAIN, L3_BOOK, TRADES


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible

async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    logging.info(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Last Price: {bid}')


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    logging.info(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} '
                 f'Top of Book: {book[BID].peekitem(-1)} Ask:  {book[ASK].peekitem(0)}')


def main():
    logging.basicConfig(level=logging.INFO)
    f = FeedHandler(log_messages_on_error=True)

    f.add_feed(BLOCKCHAIN, pairs=['BTC-USD', 'ETH-USD'], channels=[L2_BOOK],
               callbacks={
                   L2_BOOK: BookCallback(book),
                   TRADES: trade
               })

    f.run()


if __name__ == '__main__':
    main()
