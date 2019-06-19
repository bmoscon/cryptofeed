'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.mongo import TradeMongo, BookDeltaMongo, BookMongo
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase

from cryptofeed.defines import TRADES, L2_BOOK, BOOK_DELTA


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES, L2_BOOK],
                        pairs=['BTC-USD'],
                        callbacks={TRADES: TradeMongo('coinbase', collection='trades'),
                                   L2_BOOK: BookMongo('coinbase', collection='l2_book'),
                                   BOOK_DELTA: BookDeltaMongo('coinbase', collection='l2_book')}))

    f.run()


if __name__ == '__main__':
    main()
