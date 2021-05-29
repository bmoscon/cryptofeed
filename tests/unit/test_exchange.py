'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import glob
import json

import pytest

from cryptofeed.defines import CANDLES, BINANCE, BINANCE_DELIVERY, BITCOINCOM, BITFINEX, EXX, BINANCE_FUTURES, BINANCE_US, BITFLYER, BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, COINBASE, COINGECKO, DERIBIT, FTX_US, FTX, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP, KRAKEN, KRAKEN_FUTURES, KUCOIN, OKCOIN, OKEX, OPEN_INTEREST, POLONIEX, PROBIT, TICKER, TRADES, L2_BOOK, BYBIT, UPBIT
from cryptofeed.exchanges import EXCHANGE_MAP
from cryptofeed.raw_data_collection import playback
from cryptofeed.symbols import Symbols


# Some exchanges discard messages so we cant use a normal in == out comparison for testing purposes


lookup_table = {
    BINANCE: {L2_BOOK: 590, TICKER: 570, TRADES: 24, CANDLES: 20},
    BINANCE_US: {TICKER: 458, TRADES: 18, L2_BOOK: 797},
    BINANCE_FUTURES: {CANDLES: 99, L2_BOOK: 997, TICKER: 1959, TRADES: 185},
    BINANCE_DELIVERY: {L2_BOOK: 2212, TICKER: 7082, TRADES: 131},
    BITCOINCOM: {L2_BOOK: 699, TICKER: 150, TRADES: 5},
    BITFINEX: {L2_BOOK: 1600, TICKER: 21, TRADES: 210},
    BITFLYER: {L2_BOOK: 713, TICKER: 226, TRADES: 31},
    BITMAX: {L2_BOOK: 279, TRADES: 4},
    BITMEX: {L2_BOOK: 1862, TICKER: 429, TRADES: 18},
    BITSTAMP: {TRADES: 16, L2_BOOK: 538},
    BITTREX: {TICKER: 22, TRADES: 1, L2_BOOK: 303},
    BLOCKCHAIN: {L2_BOOK: 558},
    BYBIT: {TRADES: 251, L2_BOOK: 4278},
    COINBASE: {L2_BOOK: 9729, TICKER: 107, TRADES: 107},
    DERIBIT: {L2_BOOK: 56, OPEN_INTEREST: 10, TICKER: 92},
    FTX: {L2_BOOK: 1276, TICKER: 1313, TRADES: 37},
    FTX_US: {L2_BOOK: 415, TICKER: 421},
    GEMINI: {L2_BOOK: 935, TRADES: 51},
    HITBTC: {L2_BOOK: 840, TICKER: 165, TRADES: 1008},
    HUOBI_DM:  {L2_BOOK: 4456, TRADES: 128},
    HUOBI_SWAP:  {L2_BOOK: 5062, TRADES: 226},
    HUOBI: {L2_BOOK: 292, TRADES: 73},
    KRAKEN_FUTURES: {TICKER: 541, TRADES: 3, L2_BOOK: 6538},
    KRAKEN: {L2_BOOK: 4279, TICKER: 18, TRADES: 10},
    OKCOIN: {L2_BOOK: 1620, TICKER: 30, TRADES: 30},
    OKEX: {L2_BOOK: 6974, OPEN_INTEREST: 32, TICKER: 99, TRADES: 75},    
    POLONIEX: {TICKER: 33, TRADES: 2, L2_BOOK: 164},
    UPBIT:  {L2_BOOK: 145, TRADES: 304},
    GATEIO: {CANDLES: 14, L2_BOOK: 159, TICKER: 22, TRADES: 9},
    PROBIT:  {L2_BOOK: 27, TRADES: 1001},
    KUCOIN: {TRADES: 18, TICKER: 830, CANDLES: 6, L2_BOOK: 3823}
}


def get_message_count(filenames: str):
    counter = 0
    for filename in filenames:
        if '.ws.' not in filename:
            continue
        with open(filename, 'r') as fp:
            for line in fp.readlines():
                if line == "\n":
                    continue
                start = line[:3]
                if start == 'wss':
                    continue
                counter += 1
    return counter


@pytest.mark.parametrize("exchange", [e for e in EXCHANGE_MAP.keys() if e not in [COINGECKO, EXX]])
def test_exchange_playback(exchange):
    Symbols.clear()
    dir = os.path.dirname(os.path.realpath(__file__))
    pcap = glob.glob(f"{dir}/../../sample_data/{exchange}.*")

    results = playback(exchange, pcap)
    message_count = get_message_count(pcap)

    assert results['messages_processed'] == message_count
    assert lookup_table[exchange] == results['callbacks']
    Symbols.clear()