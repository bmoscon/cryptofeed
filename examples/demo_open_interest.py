'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.arctic import TradeArctic, OpenInterestArctic
from cryptofeed.backends.aggregate import OHLCV

from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex
from cryptofeed.defines import TRADES, OPEN_INTEREST


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[TRADES, OPEN_INTEREST], callbacks={
               OPEN_INTEREST: OpenInterestArctic('cryptofeed-test2'), TRADES: TradeArctic('cryptofeed-test2')}))

    f.run()


if __name__ == '__main__':
    main()
