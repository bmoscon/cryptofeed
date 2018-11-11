'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange
from cryptofeed.coinbase.pairs import coinbase_pair_mapping
from cryptofeed.poloniex.pairs import poloniex_pair_mapping
from cryptofeed.bitfinex.pairs import bitfinex_pair_mapping
from cryptofeed.gemini.pairs import gemini_pair_mapping
from cryptofeed.hitbtc.pairs import hitbtc_pair_mapping
from cryptofeed.bitstamp.pairs import bitstamp_pair_mapping
from cryptofeed.exchanges import COINBASE, POLONIEX, BITFINEX, HITBTC, GEMINI, BITSTAMP


def test_coinbase_pair_conversions():
    for _, pair in coinbase_pair_mapping.items():
        assert(pair_exchange_to_std(pair) == pair_std_to_exchange(pair, COINBASE))


def test_poloniex_pair_conversions():
    for _, pair in poloniex_pair_mapping.items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, POLONIEX))


def test_bitfinex_pair_conversions():
    for _, pair in bitfinex_pair_mapping.items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, BITFINEX))


def test_hitbtc_pair_conversions():
    for _, pair in hitbtc_pair_mapping.items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, HITBTC))


def test_gemini_pair_conversions():
    for _, pair in gemini_pair_mapping.items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, GEMINI))


def test_bitstamp_pair_conversions():
    for _, pair in bitstamp_pair_mapping.items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, BITSTAMP))
