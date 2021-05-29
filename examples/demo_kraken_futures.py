'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES
from cryptofeed.exchanges import KrakenFutures


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def funding(**kwargs):
    print(f"Funding: {kwargs}")


async def oi(feed, symbol, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} open interest: {open_interest}')


def main():
    fh = FeedHandler()

    sub = {OPEN_INTEREST: ['PI-BTC-USD', 'PI-ETH-USD'], TRADES: ['PI-BTC-USD'], TICKER: ['PI-BTC-USD', 'PI-ETH-USD'], L2_BOOK: ['PI-ETH-USD', 'PI-XRP-USD'], FUNDING: ['PI-BTC-USD']}
    fh.add_feed(KrakenFutures(subscription=sub, callbacks={OPEN_INTEREST: oi, FUNDING: funding, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    fh.run()


if __name__ == '__main__':
    main()
