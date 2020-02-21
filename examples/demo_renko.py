'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback
from cryptofeed.backends.aggregate import RenkoFixed

from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex
from cryptofeed.defines import TRADES

from datetime import datetime


async def renko(data=None):
    print(datetime.utcnow(), data)


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[TRADES], callbacks={
               TRADES: RenkoFixed(Callback(renko), brick_size=3)}))

    f.run()


if __name__ == '__main__':
    main()
