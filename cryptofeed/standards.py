'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Contains all code to normalize and standardize the differences
between exchanges. These include trading pairs, timestamps, and
data channel names
'''
from datetime import datetime as dt
import calendar
import logging

from cryptofeed.defines import (L2_BOOK, L3_BOOK, TRADES, TICKER, VOLUME, FUNDING, UNSUPPORTED, BITFINEX,
                                POLONIEX, HITBTC, BITSTAMP, COINBASE, BITMEX, KRAKEN, BINANCE, EXX, HUOBI, HUOBI_US, OKCOIN,
                                OKEX, COINBENE, TRADES_SWAP, TICKER_SWAP, L2_BOOK_SWAP)
from cryptofeed.pairs import gen_pairs


LOG = logging.getLogger('feedhandler')


_std_trading_pairs = {}
_exchange_to_std = {}


def load_exchange_pair_mapping(exchange):
    if exchange == BITMEX:
        return
    mapping = gen_pairs(exchange)
    for std, exch in mapping.items():
        _exchange_to_std[exch] = std
        if std in _std_trading_pairs:
            _std_trading_pairs[std][exchange] = exch
        else:
            _std_trading_pairs[std] = {exchange: exch}


def pair_std_to_exchange(pair, exchange):
    if pair in _std_trading_pairs:
        try:
            return _std_trading_pairs[pair][exchange]
        except KeyError:
            raise KeyError("{} is not configured/availble for {}".format(
                pair, exchange))
    else:
        if exchange == BITFINEX and '-' not in pair:
            return "f{}".format(pair)
        return None


def pair_exchange_to_std(pair):
    if pair in _exchange_to_std:
        return _exchange_to_std[pair]
    if pair[0] == 'f':
        return pair[1:]
    return None


def timestamp_normalize(exchange, ts):
    if exchange == BITMEX or exchange == COINBASE:
        ts = dt.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        return calendar.timegm(ts.utctimetuple())
    elif exchange in  {HUOBI, BITFINEX}:
        return ts / 1000.0
    return ts


_feed_to_exchange_map = {
    L2_BOOK: {
        BITFINEX: 'book-P0-F0-100',
        POLONIEX: UNSUPPORTED,
        HITBTC: 'subscribeOrderbook',
        COINBASE: 'level2',
        BITMEX: 'orderBook10',
        BITSTAMP: 'order_book',
        KRAKEN: 'book',
        BINANCE: 'depth20',
        EXX: 'ENTRUST_ADD',
        HUOBI: 'depth.step0',
        HUOBI_US: 'depth.step0',
        OKCOIN: 'spot/depth',
        OKEX: 'spot/depth',
        COINBENE: L2_BOOK
    },
    L3_BOOK: {
        BITFINEX: 'book-R0-F0-100',
        BITSTAMP: UNSUPPORTED,
        HITBTC: UNSUPPORTED,
        COINBASE: 'full',
        BITMEX: 'orderBookL2',
        POLONIEX: UNSUPPORTED,  # supported by specifying a trading pair as the channel,
        KRAKEN: UNSUPPORTED,
        BINANCE: UNSUPPORTED,
        EXX: UNSUPPORTED,
        HUOBI: UNSUPPORTED,
        HUOBI_US: UNSUPPORTED,
        OKCOIN: UNSUPPORTED,
        OKEX: UNSUPPORTED
    },
    TRADES: {
        POLONIEX: UNSUPPORTED,
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        COINBASE: 'matches',
        BITMEX: 'trade',
        KRAKEN: 'trade',
        BINANCE: 'trade',
        EXX: 'TRADE',
        HUOBI: 'trade.detail',
        HUOBI_US: 'trade.detail',
        OKCOIN: 'spot/trade',
        OKEX: 'spot/trade',
        COINBENE: TRADES
    },
    TICKER: {
        POLONIEX: 1002,
        HITBTC: 'subscribeTicker',
        BITFINEX: 'ticker',
        BITSTAMP: UNSUPPORTED,
        COINBASE: 'ticker',
        BITMEX: UNSUPPORTED,
        KRAKEN: TICKER,
        BINANCE: 'ticker',
        HUOBI: UNSUPPORTED,
        HUOBI_US: UNSUPPORTED,
        OKCOIN: 'spot/ticker',
        OKEX: 'spot/ticker',
        COINBENE: TICKER
    },
    VOLUME: {
        POLONIEX: 1003
    },
    FUNDING: {
        BITMEX: 'funding',
        BITFINEX: 'trades'
    },
    TRADES_SWAP: {
        OKEX: 'swap/trade'
    },
    TICKER_SWAP: {
        OKEX: 'swap/ticker'
    },
    L2_BOOK_SWAP: {
        OKEX: 'swap/depth'
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
