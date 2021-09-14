'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.arctic import FundingArctic, TickerArctic, TradeArctic
from cryptofeed.defines import FUNDING, TICKER, TRADES
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING], symbols=['BTC-USD-PERP'], callbacks={TRADES: TradeArctic('cryptofeed-test'), FUNDING: FundingArctic('cryptofeed-test')}))
    f.add_feed(Bitfinex(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeArctic('cryptofeed-test')}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerArctic('cryptofeed-test')}))
    f.run()


if __name__ == '__main__':
    main()
