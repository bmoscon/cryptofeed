'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, COINBASE, L2_BOOK, L3_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Coinbase, Gemini
from cryptofeed.pairs import set_pair_separator


async def ticker(feed, pair, bid, ask, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    set_pair_separator('/')
    f = FeedHandler()
    f.add_feed(COINBASE, pairs=['BTC/USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Gemini(pairs=['BTC/USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(config={L2_BOOK: ['ETH/USD'], L3_BOOK: ['BTC/USD']}, callbacks={L3_BOOK: BookCallback(book), L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
