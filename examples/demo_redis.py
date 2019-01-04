'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.redis import TradeRedis, FundingRedis, BookRedis
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Bitfinex, Coinbase, Gemini

from cryptofeed.defines import TRADES, FUNDING, L2_BOOK


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING], pairs=['XBTUSD'], callbacks={TRADES: TradeRedis(), FUNDING: FundingRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookRedis(depth=10)}))
    f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))

    f.run()


if __name__ == '__main__':
    main()
