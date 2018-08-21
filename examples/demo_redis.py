'''
Copyright (C) 2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.redis import TradeRedis, FundingRedis
from cryptofeed import FeedHandler
from cryptofeed import Bitmex, Bitfinex, GDAX, Gemini

from cryptofeed.defines import TRADES, FUNDING


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING], pairs=['XBTUSD'], callbacks={TRADES: TradeRedis(), FUNDING: FundingRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(GDAX(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={TRADES: TradeRedis()}))

    f.run()


if __name__ == '__main__':
    main()
