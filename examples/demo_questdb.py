'''
Copyright (C) 2018-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.quest import BookQuest, CandlesQuest, FundingQuest, TickerQuest, TradeQuest
from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Bitmex, Coinbase
from cryptofeed.exchanges.binance import Binance

QUEST_HOST = '127.0.0.1'
QUEST_PORT = 9009


def main():

    f = FeedHandler()
    f.add_feed(Bitmex(channels=[FUNDING, L2_BOOK], symbols=['BTC-USD-PERP'], callbacks={FUNDING: FundingQuest(host=QUEST_HOST, port=QUEST_PORT), L2_BOOK: BookQuest(host=QUEST_HOST, port=QUEST_PORT)}))
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeQuest(host=QUEST_HOST, port=QUEST_PORT)}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookQuest(host=QUEST_HOST, port=QUEST_PORT)}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerQuest(host=QUEST_HOST, port=QUEST_PORT)}))
    f.add_feed(Binance(candle_closed_only=False, channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesQuest(host=QUEST_HOST, port=QUEST_PORT)}))
    f.run()


if __name__ == '__main__':
    main()
