'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.arctic import OpenInterestArctic, TradeArctic
from cryptofeed.defines import OPEN_INTEREST, TRADES
from cryptofeed.exchanges import Bitmex


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(symbols=['XBTUSD'], channels=[TRADES, OPEN_INTEREST], callbacks={
               OPEN_INTEREST: OpenInterestArctic('cryptofeed-test2'), TRADES: TradeArctic('cryptofeed-test2')}))

    f.run()


if __name__ == '__main__':
    main()
