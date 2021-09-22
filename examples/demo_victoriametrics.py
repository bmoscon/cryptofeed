'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.victoriametrics import TradeVictoriaMetrics, TickerVictoriaMetrics, BookVictoriaMetrics, CandlesVictoriaMetrics
from cryptofeed.defines import TRADES, TICKER, L2_BOOK, CANDLES
from cryptofeed.exchanges import Coinbase, Binance


def main():
    addr = 'tcp://localhost'
    port = 8189

    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeVictoriaMetrics(addr, port, 'demo-trades')}))
    f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerVictoriaMetrics(addr, port, 'demo-tickers')}))
    f.add_feed(Coinbase(channels=[L2_BOOK], symbols=['BTC-USD'], callbacks={L2_BOOK: BookVictoriaMetrics(addr, port, 'demo-book')}))
    f.add_feed(Binance(channels=[CANDLES], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesVictoriaMetrics(addr, port, 'demo-candles')}))

    f.run()


if __name__ == '__main__':
    main()
