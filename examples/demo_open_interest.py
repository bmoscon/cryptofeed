'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.arctic import OpenInterestArctic
from cryptofeed.backends.aggregate import OHLCV

from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex
from cryptofeed.defines import INSTRUMENT


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[INSTRUMENT], callbacks={
               INSTRUMENT: OpenInterestArctic('cryptofeed-test')}))

    f.run()


if __name__ == '__main__':
    main()
