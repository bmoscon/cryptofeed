'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BITCOINCOM, BITFINEX, BITSTAMP, BLOCKCHAIN, COINBASE, GEMINI, HITBTC, POLONIEX
from cryptofeed.symbols import (bitcoincom_symbols, bitfinex_symbols, bitstamp_symbols, blockchain_symbols,
                              coinbase_symbols, gemini_symbols, hitbtc_symbols, poloniex_symbols)
from cryptofeed.standards import load_exchange_symbol_mapping, symbol_exchange_to_std, symbol_std_to_exchange


def test_coinbase_symbol_conversions():
    load_exchange_symbol_mapping(COINBASE)
    for _, symbol in coinbase_symbols().items():
        assert(symbol_exchange_to_std(symbol) == symbol_std_to_exchange(symbol, COINBASE))


def test_poloniex_symbol_conversions():
    load_exchange_symbol_mapping(POLONIEX)
    for _, symbol in poloniex_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, POLONIEX))


def test_bitfinex_symbol_conversions():
    load_exchange_symbol_mapping(BITFINEX)
    for _, symbol in bitfinex_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, BITFINEX))


def test_hitbtc_symbol_conversions():
    load_exchange_symbol_mapping(HITBTC)
    for _, symbol in hitbtc_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, HITBTC))


def test_gemini_symbol_conversions():
    load_exchange_symbol_mapping(GEMINI)
    for _, symbol in gemini_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, GEMINI))


def test_bitstamp_symbol_conversions():
    load_exchange_symbol_mapping(BITSTAMP)
    for _, symbol in bitstamp_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, BITSTAMP))


def test_bitcoincom_symbol_conversions():
    load_exchange_symbol_mapping(BITCOINCOM)
    for _, symbol in bitcoincom_symbols().items():
        std = symbol_exchange_to_std(symbol)
        assert(symbol == symbol_std_to_exchange(std, BITCOINCOM))


def test_blockchain_symbol_conversions():
    load_exchange_symbol_mapping(BLOCKCHAIN)
    for _, symbol in blockchain_symbols().items():
        assert(symbol_exchange_to_std(symbol) == symbol_std_to_exchange(symbol, BLOCKCHAIN))
