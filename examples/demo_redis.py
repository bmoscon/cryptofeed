'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.redis import BookStream, CandlesRedis, FundingRedis, OpenInterestRedis, TradeRedis
from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, OPEN_INTEREST, TRADES
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase, Gemini, Binance


def main():
    config = {'log': {'filename': 'redis-demo.log', 'level': 'INFO'}}
    f = FeedHandler(config=config)
    f.add_feed(Bitmex(channels=[TRADES, FUNDING, OPEN_INTEREST], symbols=['BTC-USD-PERP'], callbacks={TRADES: TradeRedis(), FUNDING: FundingRedis(), OPEN_INTEREST: OpenInterestRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookStream()}))
    f.add_feed(Gemini(symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Binance(candle_closed_only=True, symbols=['BTC-USDT'], channels=[CANDLES], callbacks={CANDLES: CandlesRedis(score_key='start')}))

    f.run()


if __name__ == '__main__':
    main()
