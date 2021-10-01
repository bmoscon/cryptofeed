'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

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


def stop():
    loop = asyncio.get_event_loop()
    loop.stop()


def add_new_feed():
    loop = asyncio.get_event_loop()
    f.add_feed(Coinbase(symbols=['ETH-USD'], channels=[TRADES], callbacks={TRADES: trade}), loop=loop)


def main():
    loop = asyncio.get_event_loop()
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: trade}))
    f.run(start_loop=False)

    loop.call_later(2, add_new_feed)
    loop.call_later(15, stop)
    loop.run_forever()


if __name__ == '__main__':
    main()
