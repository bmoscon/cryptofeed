'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
import calendar

from cryptofeed.exchanges import COINBASE, GEMINI, BITFINEX, BITSTAMP, HITBTC, BITMEX, POLONIEX, KRAKEN, BINANCE
from cryptofeed.poloniex.pairs import poloniex_pair_mapping
from cryptofeed.binance.pairs import binance_pair_mapping
from cryptofeed.hitbtc.pairs import hitbtc_pair_mapping
from cryptofeed.kraken.pairs import kraken_pair_mapping
from cryptofeed.bitfinex.pairs import bitfinex_pair_mapping
from cryptofeed.bitstamp.pairs import bitstamp_pair_mapping
from cryptofeed.coinbase.pairs import coinbase_pair_mapping
from cryptofeed.gemini.pairs import gemini_pair_mapping


_std_trading_pairs = {}
_exchange_to_std = {}

mappings = {
    GEMINI: gemini_pair_mapping,
    COINBASE: coinbase_pair_mapping,
    BITSTAMP: bitstamp_pair_mapping,
    BITFINEX: bitfinex_pair_mapping,
    BINANCE: binance_pair_mapping,
    HITBTC: hitbtc_pair_mapping,
    KRAKEN: kraken_pair_mapping,
    POLONIEX: poloniex_pair_mapping
}

for exchange, mapping in mappings.items():
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
    elif exchange == 'BITFINEX':
        return ts / 1000.0
    return ts
