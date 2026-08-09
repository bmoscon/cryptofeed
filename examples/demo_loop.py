'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed import FeedHandler
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def trade(t, receipt):
    print(t)


f = FeedHandler()


def add_new_feed():
    # add_feed works while the handler is running (from the loop thread)
    f.add_feed(Coinbase(symbols=['ETH-USD'], channels=[TRADES], callbacks={TRADES: trade}))


async def main():
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: trade}))
    loop = asyncio.get_running_loop()
    loop.call_later(2, add_new_feed)
    loop.call_later(15, f.request_stop)
    await f.run_async()


if __name__ == '__main__':
    asyncio.run(main())
