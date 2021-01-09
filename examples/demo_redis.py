'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.redis import BookRedis, FundingRedis, OpenInterestRedis, TradeRedis
from cryptofeed.defines import FUNDING, L2_BOOK, OPEN_INTEREST, TRADES
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase, Gemini


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING, OPEN_INTEREST], symbols=['XBTUSD'], callbacks={
               TRADES: TradeRedis(), FUNDING: FundingRedis(), OPEN_INTEREST: OpenInterestRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(max_depth=10, channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookRedis()}))
    f.add_feed(Gemini(symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))

    f.run()


if __name__ == '__main__':
    main()
