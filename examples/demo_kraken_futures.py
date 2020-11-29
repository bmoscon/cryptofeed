'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES
from cryptofeed.exchanges import KrakenFutures


async def trade(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def ticker(feed, pair, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def funding(**kwargs):
    print(f"Funding: {kwargs}")


async def oi(feed, pair, open_interest, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} open interest: {open_interest}')


def main():
    fh = FeedHandler()

    config = {OPEN_INTEREST: ['PI_XBTUSD', 'PI_ETHUSD'], TRADES: ['PI_XBTUSD'], TICKER: ['PI_XBTUSD', 'PI_ETHUSD'], L2_BOOK: ['PI_ETHUSD', 'PI_XBTUSD'], FUNDING: ['PI_XBTUSD']}
    fh.add_feed(KrakenFutures(config=config, callbacks={OPEN_INTEREST: oi, FUNDING: funding, TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    fh.run()


if __name__ == '__main__':
    main()
