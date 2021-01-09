'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.providers import Coingecko
from cryptofeed.defines import MARKET_INFO


async def minfo(**kwargs):
    print(kwargs)


def main():
    f = FeedHandler()
    f.add_feed(Coingecko(symbols=['BTC-USD', 'ETH-EUR'], channels=[MARKET_INFO], callbacks={MARKET_INFO: minfo}))
    f.run()


if __name__ == '__main__':
    main()
