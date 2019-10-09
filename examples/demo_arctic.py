'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.arctic import TradeArctic, FundingArctic, TickerArctic
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Bitfinex, Coinbase

from cryptofeed.defines import TRADES, FUNDING, TICKER


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING], pairs=['XBTUSD'], callbacks={TRADES: TradeArctic('cryptofeed-test'), FUNDING: FundingArctic('cryptofeed-test')}))
    f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeArctic('cryptofeed-test')}))
    f.add_feed(Coinbase(channels=[TICKER], pairs=['BTC-USD'], callbacks={TICKER: TickerArctic('cryptofeed-test')}))
    f.run()


if __name__ == '__main__':
    main()
