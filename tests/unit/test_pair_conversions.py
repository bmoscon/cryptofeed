'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange
from cryptofeed.coinbase.pairs import coinbase_trading_pairs
from cryptofeed.poloniex.pairs import poloniex_trading_pairs
from cryptofeed.bitfinex.pairs import bitfinex_trading_pairs
from cryptofeed.gemini.pairs import gemini_trading_pairs
from cryptofeed.hitbtc.pairs import hitbtc_trading_pairs
from cryptofeed.bitstamp.pairs import bitstamp_trading_pairs


def test_coinbase_pair_conversions():
    for pair in coinbase_trading_pairs:
        assert(pair_exchange_to_std(pair) == pair_std_to_exchange(pair, 'COINBASE'))


def test_poloniex_pair_conversions():
    for pair in poloniex_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'POLONIEX'))


def test_bitfinex_pair_conversions():
    for pair in bitfinex_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'BITFINEX'))


def test_hitbtc_pair_conversions():
    for pair in hitbtc_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'HITBTC'))


def test_gemini_pair_conversions():
    for pair in gemini_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'GEMINI'))


def test_bitstamp_pair_conversions():
    for pair in bitstamp_trading_pairs:
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, 'BITSTAMP'))