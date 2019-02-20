'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback
from cryptofeed.backends.aggregate import OHLCV

from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import TRADES


async def ohlcv(data=None):
    print(data)


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(pairs=['BTC-USD', 'ETH-USD', 'BCH-USD'], channels=[TRADES], callbacks={TRADES: OHLCV(Callback(ohlcv), window=300)}))

    f.run()


if __name__ == '__main__':
    main()
