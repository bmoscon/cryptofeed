'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
import calendar

from cryptofeed.exchanges import COINBASE, GEMINI, BITFINEX, BITSTAMP, HITBTC, BITMEX, POLONIEX, KRAKEN, BINANCE
from cryptofeed.poloniex.pairs import poloniex_trading_pairs
from cryptofeed.binance.pairs import binance_pair_mapping
from cryptofeed.hitbtc.pairs import hitbtc_pair_mapping
from cryptofeed.kraken.pairs import get_kraken_pairs


_std_trading_pairs = {
    'BTC-USD': {
        COINBASE: 'BTC-USD',
        BITFINEX: 'tBTCUSD',
        GEMINI: 'BTCUSD',
        BITSTAMP: 'btcusd'
    },
    'ETH-USD': {
        GEMINI: 'ETHUSD',
        COINBASE: 'ETH-USD',
        BITFINEX: 'tETHUSD',
        BITSTAMP: 'ethusd'
    },
    'ETH-BTC': {
        GEMINI: 'ETHBTC',
        COINBASE: 'ETH-BTC',
        BITFINEX: 'tETHBTC',
        BITSTAMP: 'ethbtc'
    },
    'BCH-USD': {
        COINBASE: 'BCH-USD',
        BITFINEX: 'tBCHUSD',
        BITSTAMP: 'bchusd'
    },
    'LTC-EUR': {
        COINBASE: 'LTC-EUR',
        BITSTAMP: 'ltceur'
    },
    'LTC-USD': {
        COINBASE: 'LTC-USD',
        BITFINEX: 'tLTCUSD',
        BITSTAMP: 'ltcusd'
    },
    'LTC-BTC': {
        COINBASE: 'LTC-BTC',
        BITFINEX: 'tLTCBTC',
        BITSTAMP: 'ltcbtc'
    },
    'ETH-EUR': {
        COINBASE: 'ETH-EUR',
        BITSTAMP: 'etheur'
    },
    'BTC-GBP': {
        COINBASE: 'BTC-GBP'
    },
    'BTC-EUR': {
        COINBASE: 'BTC-EUR',
        BITFINEX: 'tBTCEUR',
        BITSTAMP: 'btceur'
    },
    'BCH-ETH': {
        BITFINEX: 'tBCHETH',
    },
    'DATA-BTC': {
        BITFINEX: 'tDATABTC',
    },
    'ETC-BTC': {
        BITFINEX: 'tETCBTC',
    },
    'GNT-BTC': {
        BITFINEX: 'tGNTBTC'
    },
    'QTUM-BTC': {
        BITFINEX: 'tQTUMBTC'
    },
    'SAN-USD': {
        BITFINEX: 'tSANUSD'
    },
    'OMG-ETH': {
        BITFINEX: 'tOMGETH',
    },
    'ETC-USD': {
        BITFINEX: 'tETCUSD',
    },
    'DASH-USD': {
        BITFINEX: 'tDASHUSD',
    },
    'RRT-USD': {
        BITFINEX: 'tRRTUSD'
    },
    'SAN-BTC': {
        BITFINEX: 'tSANBTC'
    },
    'GNT-USD': {
        BITFINEX: 'tGNTUSD'
    },
    'IOTA-EUR': {
        BITFINEX: 'tIOTAEUR'
    },
    'YYW-BTC': {
        BITFINEX: 'tYYWBTC'
    },
    'BCH-BTC': {
        BITFINEX: 'tBCHBTC',
        BITSTAMP: 'bchbtc'
    },
    'NEO-USD': {
        BITFINEX: 'tNEOUSD',
    },
    'EDO-BTC': {
        BITFINEX: 'tEDOBTC',
    },
    'EDO-ETH': {
        BITFINEX: 'tEDOETH',
    },
    'QASH-USD': {
        BITFINEX: 'tQASHUSD'
    },
    'QTUM-USD': {
        BITFINEX: 'tQTUMUSD'
    },
    'BTG-BTC': {
        BITFINEX: 'tBTGBTC',
    },
    'ZEC-BTC': {
        BITFINEX: 'tZECBTC',
    },
    'XRP-BTC': {
        BITFINEX: 'tXRPBTC',
        BITSTAMP: 'xrpbtc'
    },
    'AVT-USD': {
        BITFINEX: 'tAVTUSD'
    },
    'XRP-USD': {
        BITFINEX: 'tXRPUSD',
        BITSTAMP: 'xrpusd'
    },
    'XMR-BTC': {
        BITFINEX: 'tXMRBTC',
    },
    'OMG-BTC': {
        BITFINEX: 'tOMGBTC',
    },
    'IOTA-USD': {
        BITFINEX: 'tIOTAUSD'
    },
    'ETP-USD': {
        BITFINEX: 'tETPUSD',
    },
    'IOTA-BTC': {
        BITFINEX: 'tIOTABTC'
    },
    'EDO-USD': {
        BITFINEX: 'tEDOUSD',
    },
    'NEO-ETH': {
        BITFINEX: 'tNEOETH',
    },
    'SNT-USD': {
        BITFINEX: 'tSNTUSD'
    },
    'BTG-USD': {
        BITFINEX: 'tBTGUSD',
    },
    'DATA-USD': {
        BITFINEX: 'tDATAUSD',
    },
    'ETP-BTC': {
        BITFINEX: 'tETPBTC',
    },
    'AVT-ETH': {
        BITFINEX: 'tAVTETH',
    },
    'SAN-ETH': {
        BITFINEX: 'tSANETH',
    },
    'EOS-ETH': {
        BITFINEX: 'tEOSETH',
    },
    'DATA-ETH': {
        BITFINEX: 'tDATAETH',
    },
    'DASH-BTC': {
        BITFINEX: 'tDASHBTC',
    },
    'XMR-USD': {
        BITFINEX: 'tXMRUSD',
    },
    'IOTA-ETH': {
        BITFINEX: 'tIOTAETH'
    },
    'YYW-ETH': {
        BITFINEX: 'tYYWETH'
    },
    'QTUM-ETH': {
        BITFINEX: 'tQTUMETH',
    },
    'YYW-USD': {
        BITFINEX: 'tYYWUSD'
    },
    'OMG-USD': {
        BITFINEX: 'tOMGUSD'
    },
    'GNT-ETH': {
        BITFINEX: 'tGNTETH'
    },
    'EOS-BTC': {
        BITFINEX: 'tEOSBTC',
    },
    'ETP-ETH': {
        BITFINEX: 'tETPETH',
    },
    'SNT-BTC': {
        BITFINEX: 'tSNTBTC',
    },
    'SNT-ETH': {
        BITFINEX: 'tSNTETH',
    },
    'QASH-BTC': {
        BITFINEX: 'tQASHBTC'
    },
    'QASH-ETH': {
        BITFINEX: 'tQASHETH'
    },
    'AVT-BTC': {
        BITFINEX: 'tAVTBTC'
    },
    'RRT-BTC': {
        BITFINEX: 'tRRTBTC'
    },
    'ZEC-USD': {
        BITFINEX: 'tZECUSD',
    },
    'NEO-BTC': {
        BITFINEX: 'tNEOBTC',
    },
    'EOS-USD': {
        BITFINEX: 'tEOSUSD',
    },
    'EUR-USD': {
        BITSTAMP: 'eurusd'
    },
    'XRP-EUR': {
        BITSTAMP: 'xrpeur'
    },
    'BCH-EUR': {
        BITSTAMP: 'bcheur'
    }
}

_exchange_to_std = {
    'BTC-USD': 'BTC-USD',
    'BTCUSD': 'BTC-USD',
    'ETHUSD': 'ETH-USD',
    'ETH-USD': 'ETH-USD',
    'ETHBTC': 'ETH-BTC',
    'ETH-BTC': 'ETH-BTC',
    'BCH-USD': 'BCH-USD',
    'LTC-USD': 'LTC-USD',
    'LTC-EUR': 'LTC-EUR',
    'LTC-BTC': 'LTC-BTC',
    'ETH-EUR': 'ETH-EUR',
    'BTC-GBP': 'BTC-GBP',
    'BTC-EUR': 'BTC-EUR',
    # Bitfinex
    'tBCHETH': 'BCH-ETH',
    'tDATABTC': 'DATA-BTC',
    'tETCBTC': 'ETC-BTC',
    'tGNTBTC': 'GNT-BTC',
    'tQTUMBTC': 'QTUM-BTC',
    'tSANUSD': 'SAN-USD',
    'tOMGETH': 'OMG-ETH',
    'tETCUSD': 'ETC-USD',
    'tDASHUSD': 'DASH-USD',
    'tRRTUSD': 'RRT-USD',
    'tLTCUSD': 'LTC-USD',
    'tSANBTC': 'SAN-BTC',
    'tGNTUSD': 'GNT-USD',
    'tIOTAEUR': 'IOTA-EUR',
    'tETHUSD': 'ETH-USD',
    'tYYWBTC': 'YYW-BTC',
    'tBCHBTC': 'BCH-BTC',
    'tNEOUSD': 'NEO-USD',
    'tEDOBTC': 'EDO-BTC',
    'tEDOETH': 'EDO-ETH',
    'tQASHUSD': 'QASH-USD',
    'tQTUMUSD': 'QTUM-USD',
    'tBTGBTC': 'BTG-BTC',
    'tZECBTC': 'ZEC-BTC',
    'tXRPBTC': 'XRP-BTC',
    'tAVTUSD': 'AVT-USD',
    'tXRPUSD': 'XRP-USD',
    'tXMRBTC': 'XMR-BTC',
    'tOMGBTC': 'OMG-BTC',
    'tIOTAUSD': 'IOTA-USD',
    'tETPUSD': 'ETP-USD',
    'tIOTABTC': 'IOTA-BTC',
    'tEDOUSD': 'EDO-USD',
    'tNEOETH': 'NEO-ETH',
    'tSNTUSD': 'SNT-USD',
    'tETHBTC': 'ETH-BTC',
    'tLTCBTC': 'LTC-BTC',
    'tBTGUSD': 'BTG-USD',
    'tDATAUSD': 'DATA-USD',
    'tETPBTC': 'ETP-BTC',
    'tAVTETH': 'AVT-ETH',
    'tSANETH': 'SAN-ETH',
    'tEOSETH': 'EOS-ETH',
    'tDATAETH': 'DATA-ETH',
    'tDASHBTC': 'DASH-BTC',
    'tBCHUSD': 'BCH-USD',
    'tXMRUSD': 'XMR-USD',
    'tIOTAETH': 'IOTA-ETH',
    'tYYWETH': 'YYW-ETH',
    'tQTUMETH': 'QTUM-ETH',
    'tYYWUSD': 'YYW-USD',
    'tOMGUSD': 'OMG-USD',
    'tGNTETH': 'GNT-ETH',
    'tEOSBTC': 'EOS-BTC',
    'tETPETH': 'ETP-ETH',
    'tBTCUSD': 'BTC-USD',
    'tSNTBTC': 'SNT-BTC',
    'tSNTETH': 'SNT-ETH',
    'tBTCEUR': 'BTC-EUR',
    'tQASHBTC': 'QASH-BTC',
    'tQASHETH': 'QASH-ETH',
    'tAVTBTC': 'AVT-BTC',
    'tRRTBTC': 'RRT-BTC',
    'tZECUSD': 'ZEC-USD',
    'tNEOBTC': 'NEO-BTC',
    'tEOSUSD': 'EOS-USD',
    # Bitstamp
    'btcusd': 'BTC-USD',
    'btceur': 'BTC-EUR',
    'eurusd': 'EUR-USD',
    'xrpusd': 'XRP-USD',
    'xrpeur': 'XRP-EUR',
    'xrpbtc': 'XRP-BTC',
    'ltcusd': 'LTC-USD',
    'ltceur': 'LTC-EUR',
    'ltcbtc': 'LTC-BTC',
    'ethusd': 'ETH-USD',
    'etheur': 'ETH-EUR',
    'ethbtc': 'ETH-BTC',
    'bchusd': 'BCH-USD',
    'bcheur': 'BCH-EUR',
    'bchbtc': 'BCH-BTC'
}

for pair in poloniex_trading_pairs:
    pairs = pair.split('_')
    std = "{}-{}".format(pairs[1], pairs[0])
    _exchange_to_std[pair] = std
    if std in _std_trading_pairs:
        _std_trading_pairs[std][POLONIEX] = pair
    else:
        _std_trading_pairs[std] = {POLONIEX: pair}

for std, exch in binance_pair_mapping.items():
    _exchange_to_std[exch] = std
    if std in _std_trading_pairs:
        _std_trading_pairs[std][BINANCE] = exch
    else:
        _std_trading_pairs[std] = {BINANCE: exch}

for std, exch in hitbtc_pair_mapping.items():
    _exchange_to_std[exch] = std
    if std in _std_trading_pairs:
        _std_trading_pairs[std][HITBTC] = exch
    else:
        _std_trading_pairs[std] = {HITBTC: exch}

kraken_pairs = get_kraken_pairs()
for kraken, std in kraken_pairs.items():
    if std in _std_trading_pairs:
        _std_trading_pairs[std][KRAKEN] = kraken
    else:
        _std_trading_pairs[std] = {KRAKEN: kraken}

_exchange_to_std.update(kraken_pairs)


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
