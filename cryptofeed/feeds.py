'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.exchanges import BITFINEX, POLONIEX, HITBTC, BITSTAMP, GDAX
from cryptofeed.defines import L2_BOOK, L3_BOOK, TRADES, TICKER, VOLUME, UNSUPPORTED

_feed_to_exchange_map = {
    L2_BOOK: {
        BITFINEX: 'book-P0-F0-25',
        POLONIEX: UNSUPPORTED,
        HITBTC: UNSUPPORTED,
        GDAX: 'level2'
    },
    L3_BOOK: {
        BITFINEX: 'book-R0-F0-100',
        HITBTC: 'subscribeOrderbook',
        BITSTAMP: 'diff_order_book',
        GDAX: 'full'
    },
    TRADES: {
        POLONIEX: UNSUPPORTED,
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        GDAX: 'ticker'
    },
    TICKER: {
        POLONIEX: 1002,
        HITBTC: 'subscribeTicker',
        BITFINEX: 'ticker',
        BITSTAMP: UNSUPPORTED,
        GDAX: 'ticker'
    },
    VOLUME: {
        POLONIEX: 1003
    }
}


def feed_to_exchange(exchange, feed):
    return _feed_to_exchange_map[feed][exchange]
