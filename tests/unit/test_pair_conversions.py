'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange, load_exchange_pair_mapping
from cryptofeed.defines import COINBASE, POLONIEX, BITFINEX, HITBTC, GEMINI, BITSTAMP
from cryptofeed.pairs import coinbase_pairs, poloniex_pairs, bitfinex_pairs, hitbtc_pairs, gemini_pairs, bitstamp_pairs


def test_coinbase_pair_conversions():
    load_exchange_pair_mapping(COINBASE)
    for _, pair in coinbase_pairs().items():
        assert(pair_exchange_to_std(pair) == pair_std_to_exchange(pair, COINBASE))


def test_poloniex_pair_conversions():
    load_exchange_pair_mapping(POLONIEX)
    for _, pair in poloniex_pairs().items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, POLONIEX))


def test_bitfinex_pair_conversions():
    load_exchange_pair_mapping(BITFINEX)
    for _, pair in bitfinex_pairs().items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, BITFINEX))


def test_hitbtc_pair_conversions():
    load_exchange_pair_mapping(HITBTC)
    for _, pair in hitbtc_pairs().items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, HITBTC))


def test_gemini_pair_conversions():
    load_exchange_pair_mapping(GEMINI)
    for _, pair in gemini_pairs().items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, GEMINI))


def test_bitstamp_pair_conversions():
    load_exchange_pair_mapping(BITSTAMP)
    for _, pair in bitstamp_pairs().items():
        std = pair_exchange_to_std(pair)
        assert(pair == pair_std_to_exchange(std, BITSTAMP))
