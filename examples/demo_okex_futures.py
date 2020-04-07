'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import OKEx
from cryptofeed.defines import L2_BOOK_FUTURES, L2_BOOK, BID, ASK, TRADES, TRADES_FUTURES, TICKER, TICKER_FUTURES


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
