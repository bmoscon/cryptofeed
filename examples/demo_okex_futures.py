'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L2_BOOK, L2_BOOK_FUTURES, TICKER, TICKER_FUTURES, TRADES, TRADES_FUTURES
from cryptofeed.exchanges import OKEx


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


def main():
    fh = FeedHandler()

    callbacks = {TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book), TICKER: TickerCallback(ticker)}
    pairs = OKEx.get_active_symbols()
    fh.add_feed(OKEx(pairs=pairs, channels=[TRADES_FUTURES, L2_BOOK_FUTURES, TICKER_FUTURES], callbacks=callbacks))

    fh.run()


if __name__ == '__main__':
    main()
