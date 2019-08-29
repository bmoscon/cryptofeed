'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.influxdb import TradeInflux, FundingInflux, BookInflux, BookDeltaInflux
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex, Coinbase

from cryptofeed.defines import TRADES, FUNDING, L2_BOOK, BOOK_DELTA


def main():
    f = FeedHandler()
    f.add_feed(Bitmex(channels=[FUNDING, L2_BOOK],pairs=['XBTUSD'], callbacks={FUNDING: FundingInflux('http://localhost:8086', 'example'), L2_BOOK: BookInflux('http://localhost:8086', 'example', numeric_type=float), BOOK_DELTA: BookDeltaInflux('http://localhost:8086', 'example', numeric_type=float)}))
    f.add_feed(Coinbase(channels=[TRADES], pairs=['BTC-USD'], callbacks={TRADES: TradeInflux('http://localhost:8086', 'example')}))
    f.add_feed(Coinbase(channels=[L2_BOOK], pairs=['BTC-USD'], callbacks={L2_BOOK: BookInflux('http://localhost:8086', 'example', numeric_type=float), BOOK_DELTA: BookDeltaInflux('http://localhost:8086', 'example', numeric_type=float)}))

    f.run()


if __name__ == '__main__':
    main()
