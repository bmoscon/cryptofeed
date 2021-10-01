'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed import FeedHandler
from cryptofeed.defines import BID, ASK, COINBASE, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Binance, Coinbase


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(t, receipt_timestamp):
    print(t)


async def trade(t, receipt_timestamp):
    print(t)


async def book(update, receipt_timestamp):
    print(f"Received update from {update.exchange}", end=' - ')
    if update.delta:
        print(f"Delta from last book contains {len(update.delta[BID]) + len(update.delta[ASK])} entries.")
    else:
        book_data = update.book.to_dict()
        print(f'Book received at {receipt_timestamp} for {update.exchange} - {update.symbol}, with {len(book_data[BID]) + len(book_data[ASK])} entries.')


async def aio_task():
    while True:
        print("Other task running")
        await asyncio.sleep(1)


def main():
    f = FeedHandler()
    f.run(start_loop=False)

    f.add_feed(Binance(symbols=['BTC-USDT'], channels=[TRADES, TICKER, L2_BOOK], callbacks={L2_BOOK: book, TRADES: trade, TICKER: ticker}))
    f.add_feed(COINBASE, symbols=['BTC-USD'], channels=[TICKER], callbacks={TICKER: ticker})
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: trade}))
    f.add_feed(Coinbase(subscription={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD', 'BTC-USD']}, callbacks={TRADES: trade, L2_BOOK: book}))

    loop = asyncio.get_event_loop()
    loop.create_task(aio_task())
    loop.run_forever()


if __name__ == '__main__':
    main()
