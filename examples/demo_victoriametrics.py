'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.victoriametrics import TradeVictoriaMetrics
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


def main():
    addr = 'tcp://localhost'
    port = 8189

    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks={TRADES: TradeVictoriaMetrics(addr, port, 'demo-trades')}))

    f.run()


if __name__ == '__main__':
    main()
