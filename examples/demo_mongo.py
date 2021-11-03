'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.mongo import BookMongo, TradeMongo, TickerMongo
from cryptofeed.defines import L2_BOOK, TRADES, TICKER
from cryptofeed.exchanges import Coinbase


def main():
    """
    Because periods cannot be in keys in documents in mongo, the bids and asks dictionaries
    are converted to BSON. They will need to be decoded after being read
    """
    f = FeedHandler()
    f.add_feed(Coinbase(max_depth=10, channels=[L2_BOOK, TRADES, TICKER],
                        symbols=['BTC-USD'],
                        callbacks={TRADES: TradeMongo('coinbase', collection='trades'),
                                   L2_BOOK: BookMongo('coinbase', collection='l2_book'),
                                   TICKER: TickerMongo('coinbase', collection='ticker')
                                   }))

    f.run()


if __name__ == '__main__':
    main()
