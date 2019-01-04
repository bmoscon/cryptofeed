'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.arctic import TradeArctic, FundingArctic
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Bitfinex

from cryptofeed.defines import TRADES, FUNDING


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING], pairs=['XBTUSD'], callbacks={TRADES: TradeArctic('cryptofeed-test'), FUNDING: FundingArctic('cryptofeed-test')}))
    f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeArctic('cryptofeed-test')}))

    f.run()


if __name__ == '__main__':
    main()
