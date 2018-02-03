'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.exchanges import BITFINEX, POLONIEX
from cryptofeed.defines import L2_BOOK, L3_BOOK, TRADES, TICKER



_exchange_to_feed_map = {
        
}

_feed_to_exchange_map = {
    L2_BOOK: {BITFINEX: 'book-P0-F0-25'},
    L3_BOOK: {BITFINEX: 'book-R0-F0-100'},
    TRADES:  { },
    TICKER:  {POLONIEX: 1002},
    VOLUME:  {POLONIEX: 1003}
}


def feed_to_exchange(exchange, feed):
    return _feed_to_exchange_map[feed][exchange]
