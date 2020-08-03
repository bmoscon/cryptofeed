'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TickerCallback, TradeCallback
from cryptofeed.defines import BID, ASK, COINBASE, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Binance, Coinbase


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, pair, bid, ask):
    print(f'Feed: {feed} Pair: {pair} Bid: {bid} Ask: {ask}')


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {pair} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, pair, book, timestamp):
    print(f'Timestamp: {timestamp} Feed: {feed} Pair: {pair} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def aio_task():
    while True:
        print("Other task running")
        await asyncio.sleep(1)


def main():
    f = FeedHandler()
    # Note: EXX is extremely unreliable - sometimes a connection can take many many retries
    # f.add_feed(EXX(pairs=['BTC-USDT'], channels=[L2_BOOK, TRADES], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade)}))
    f.add_feed(Binance(pairs=['BTC-USDT'], channels=[TRADES, TICKER, L2_BOOK], callbacks={L2_BOOK: BookCallback(book), TRADES: TradeCallback(trade), TICKER: TickerCallback(ticker)}))
    f.add_feed(COINBASE, pairs=['BTC-USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)})
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TRADES], callbacks={TRADES: TradeCallback(trade)}))
    f.add_feed(Coinbase(config={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: TradeCallback(trade), L2_BOOK: BookCallback(book)}))

    f.run(start_loop=False)

    loop = asyncio.get_event_loop()
    loop.create_task(aio_task())
    loop.run_forever()


if __name__ == '__main__':
    main()
