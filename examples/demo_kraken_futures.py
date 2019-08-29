'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import KrakenFutures
from cryptofeed.defines import L2_BOOK, BID, ASK, TRADES, TICKER


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def ticker(feed, pair, bid, ask):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


def main():
    fh = FeedHandler()

    config = {TRADES: ['PI_XBTUSD'], TICKER: ['PI_XBTUSD', 'PI_ETHUSD'], L2_BOOK: ['PI_XBTUSD']}
    fh.add_feed(KrakenFutures(config=config, callbacks={TICKER: TickerCallback(ticker), TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    fh.run()


if __name__ == '__main__':
    main()
