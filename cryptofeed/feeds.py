'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.exchanges import BITFINEX, POLONIEX, HITBTC, BITSTAMP, GDAX, BITMEX
from cryptofeed.defines import L2_BOOK, L3_BOOK, TRADES, TICKER, VOLUME, FUNDING, UNSUPPORTED
from cryptofeed.standards import pair_std_to_exchange


LOG = logging.getLogger('feedhandler')


_feed_to_exchange_map = {
    L2_BOOK: {
        BITFINEX: 'book-P0-F0-100',
        POLONIEX: UNSUPPORTED,
        HITBTC: 'subscribeOrderbook',
        GDAX: 'level2',
        BITMEX: 'orderBook10',
        BITSTAMP: 'order_book'
    },
    L3_BOOK: {
        BITFINEX: 'book-R0-F0-100',
        BITSTAMP: UNSUPPORTED,
        HITBTC: UNSUPPORTED,
        GDAX: 'full',
        BITMEX: 'orderBookL2',
        POLONIEX: UNSUPPORTED, # supported by specifying a trading pair as the channel
    },
    TRADES: {
        POLONIEX: UNSUPPORTED,
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        GDAX: 'matches',
        BITMEX: 'trade'
    },
    TICKER: {
        POLONIEX: 1002,
        HITBTC: 'subscribeTicker',
        BITFINEX: 'ticker',
        BITSTAMP: UNSUPPORTED,
        GDAX: 'ticker',
        BITMEX: UNSUPPORTED
    },
    VOLUME: {
        POLONIEX: 1003
    },
    FUNDING: {
        BITMEX: 'funding',
        BITFINEX: 'trades'
    }
}


def feed_to_exchange(exchange, feed):
    if exchange == POLONIEX:
        if feed not in _feed_to_exchange_map:
            return pair_std_to_exchange(feed, POLONIEX)

    ret = _feed_to_exchange_map[feed][exchange]
    if ret == UNSUPPORTED:
        LOG.error("{} is not supported on {}".format(feed, exchange))
        raise ValueError("{} is not supported on {}".format(feed, exchange))
    return ret
