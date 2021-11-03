'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.aggregate import OHLCV
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def ohlcv(data):
    print(data)


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(symbols=['BTC-USD', 'ETH-USD', 'BCH-USD'], channels=[TRADES], callbacks={TRADES: OHLCV(ohlcv, window=10)}))

    f.run()


if __name__ == '__main__':
    main()
