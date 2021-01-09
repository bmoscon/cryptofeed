'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, COINBASE, L2_BOOK, L3_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Coinbase, Gemini
from cryptofeed.symbols import set_symbol_separator


async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


def main():
    set_symbol_separator('/')
    f = FeedHandler()
    f.add_feed(COINBASE, symbols=['BTC/USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Gemini(symbols=['BTC/USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(subscription={L2_BOOK: ['ETH/USD'], L3_BOOK: ['BTC/USD']}, callbacks={L3_BOOK: BookCallback(book), L2_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()
