'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.redis import BookDeltaStream, BookStream, CandlesRedis, FundingRedis, OpenInterestRedis, TradeRedis
from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, OPEN_INTEREST, TRADES, BOOK_DELTA
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase, Gemini, Binance


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[TRADES, FUNDING, OPEN_INTEREST], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis(), FUNDING: FundingRedis(), OPEN_INTEREST: OpenInterestRedis()}))
    f.add_feed(Bitfinex(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={BOOK_DELTA: BookDeltaStream(), L2_BOOK: BookStream()}))
    f.add_feed(Gemini(symbols=['BTC-USD'], callbacks={TRADES: TradeRedis()}))
    f.add_feed(Binance(candle_closed_only=True, symbols=['BTC-USDT'], channels=[CANDLES], callbacks={CANDLES: CandlesRedis(score_key='start')}))

    f.run()


if __name__ == '__main__':
    main()
