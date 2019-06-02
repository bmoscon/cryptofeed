'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.influxdb import TradeInflux, FundingInflux, BookInflux, BookDeltaInflux
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Coinbase

from cryptofeed.defines import TRADES, FUNDING, L2_BOOK, L3_BOOK, BOOK_DELTA


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[FUNDING,L3_BOOK],pairs=['XBTUSD'],callbacks={FUNDING: FundingInflux('http://localhost:8086', 'example'), L3_BOOK: BookInflux('http://localhost:8086', 'example', depth=10)}))
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeInflux('http://localhost:8086', 'example')}))
    f.add_feed(Coinbase(channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookInflux('http://localhost:8086', 'example'), BOOK_DELTA: BookDeltaInflux('http://localhost:8086', 'example')}))

    f.run()


if __name__ == '__main__':
    main()
