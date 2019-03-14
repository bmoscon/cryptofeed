'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.mongo import TradeMongo
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase

from cryptofeed.defines import TRADES


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeMongo('coinbase', collection='trades')}))

    f.run()


if __name__ == '__main__':
    main()
