'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time

import pandas as pd
from arctic import Arctic

from cryptofeed.callback import TickerCallback
from cryptofeed import FeedHandler
from cryptofeed import GDAX
from cryptofeed.defines import BID, ASK, TICKER


a = Arctic('127.0.0.1')
a.initialize_library('gdax.ticker')
lib = a['gdax.ticker']


async def ticker(feed, pair, bid, ask):
    ts = time.time()
    df = pd.DataFrame({'time': [ts], 'bid': [float(bid)], 'ask': [float(ask)]})
    lib.append('BTC-USD', df)


def main():
    f = FeedHandler()
    f.add_feed(GDAX(pairs=['BTC-USD'], channels=[TICKER], callbacks={TICKER: TickerCallback(ticker)}))
    f.run()


if __name__ == '__main__':
    main()
