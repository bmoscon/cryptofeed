'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime

from cryptofeed import FeedHandler
from cryptofeed.backends.aggregate import RenkoFixed
from cryptofeed.callback import Callback
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Bitmex


async def renko(data=None):
    print(datetime.utcnow(), data)


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(symbols=['XBTUSD'], channels=[TRADES], callbacks={
               TRADES: RenkoFixed(Callback(renko), brick_size=3)}))

    f.run()


if __name__ == '__main__':
    main()
