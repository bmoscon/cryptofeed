'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, FUNDING, L2_BOOK, L2_BOOK_SWAP, OPEN_INTEREST, TRADES, TRADES_SWAP
from cryptofeed.exchanges import OKEx


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def open_interest(feed, pair, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} open interest: {open_interest}')


async def funding(**kwargs):
    print(f"Funding: {kwargs}")


def main():
    fh = FeedHandler()

    fh.add_feed(OKEx(pairs=['EOS-USD-SWAP'], channels=[TRADES_SWAP, L2_BOOK_SWAP, OPEN_INTEREST, FUNDING], callbacks={FUNDING: funding, OPEN_INTEREST: open_interest, TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    fh.run()


if __name__ == '__main__':
    main()
