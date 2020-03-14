'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.redis import TradeRedis, FundingRedis, BookRedis, OpenInterestRedis
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Bitfinex, Coinbase, Gemini

from cryptofeed.defines import TRADES, FUNDING, L2_BOOK, OPEN_INTEREST


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING, OPEN_INTEREST], pairs=['XBTUSD'], callbacks={
               TRADES: TradeRedis(), FUNDING: FundingRedis(), OPEN_INTEREST: OpenInterestRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(max_depth=10, channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookRedis()}))
    f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))

    f.run()


if __name__ == '__main__':
    main()
