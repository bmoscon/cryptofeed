'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import glob
import json

import pytest

from cryptofeed.util.async_file import playback
from cryptofeed.defines import BINANCE, BINANCE_DELIVERY, BITCOINCOM, BITFINEX, EXX, BINANCE_FUTURES, BINANCE_US, BITFLYER, BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, COINBASE, COINGECKO, DERIBIT, FTX_US, FTX, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP, KRAKEN, KRAKEN_FUTURES, OKCOIN, OKEX, OPEN_INTEREST, POLONIEX, PROBIT, TICKER, TRADES, L2_BOOK, BYBIT, UPBIT, WHALE_ALERT
from cryptofeed.feedhandler import _EXCHANGES


# Some exchanges discard messages so we cant use a normal in == out comparison for testing purposes


lookup_table = {
    BITSTAMP: {TRADES: 32, L2_BOOK: 3109},
    POLONIEX: {TICKER: 56, TRADES: 2, L2_BOOK: 356}, # With Poloniex you sub to a channel, not a symbol, so in != out
    OKCOIN: [{TICKER: 53, TRADES: 44, L2_BOOK: 3516}, {L2_BOOK: 3500, TICKER: 53, TRADES: 44}],
    OKEX: [{L2_BOOK: 11992, OPEN_INTEREST: 30, TICKER: 156, TRADES: 163}, {L2_BOOK: 12034, OPEN_INTEREST: 30, TICKER: 156, TRADES: 163}],
    KRAKEN_FUTURES: {TICKER: 3041, TRADES: 93, L2_BOOK: 62073},
    BITTREX: {TICKER: 170, TRADES: 8, L2_BOOK: 1083},
    BINANCE_US: {TICKER: 2624, TRADES: 188, L2_BOOK: 3185},
    BYBIT: {TRADES: 149, L2_BOOK: 9031},
    HITBTC: {TICKER: 927, TRADES: 1016, L2_BOOK: 3248},
    BINANCE_FUTURES: {TICKER: 3424, TRADES: 574, L2_BOOK: 4395},
    BINANCE_DELIVERY: {L2_BOOK: 9323, TICKER: 24861, TRADES: 473},
    HUOBI_DM:  {L2_BOOK: 19965, TRADES: 467},
    HUOBI_SWAP:  {L2_BOOK: 16689, TRADES: 197},
    HUOBI: {L2_BOOK: 956, TRADES: 30},
    BITMEX: {L2_BOOK: 6393, TICKER: 1836, TRADES: 122},
    BINANCE: {L2_BOOK: 4642, TICKER: 5408, TRADES: 1240},
    FTX_US: {L2_BOOK: 1933, TICKER: 1960, TRADES: 4},
    FTX: {L2_BOOK: 3377, TICKER: 3420, TRADES: 81},
    BLOCKCHAIN: {L2_BOOK: 3725},
    GEMINI: {L2_BOOK: 1758, TRADES: 22},
    DERIBIT: {L2_BOOK: 187, OPEN_INTEREST: 10, TICKER: 273},
    PROBIT:  {L2_BOOK: 24, TRADES: 1003},
    UPBIT:  {L2_BOOK: 1061, TRADES: 672},
    COINBASE: {L2_BOOK: 42586, TICKER: 301, TRADES: 301},
    GATEIO: {L2_BOOK: 317, TRADES: 1027},
    BITFLYER: {L2_BOOK: 2857, TICKER: 933, TRADES: 115},
    KRAKEN: [{L2_BOOK: 14506}, {TRADES: 28}, {TICKER: 22}],
    BITMAX: {L2_BOOK: 1525, TRADES: 11},
    BITCOINCOM: {L2_BOOK: 4255, TICKER: 971, TRADES: 69},
    BITFINEX: {L2_BOOK: 22474, TICKER: 58, TRADES: 248},

}


def get_message_count(filename):
    with open(filename, 'r') as fp:
        counter = 0
        next(fp)
        for line in fp.readlines():
            if line == "\n":
                continue
            start = line[:3]
            if start == 'wss':
                continue
            counter += 1
        return counter


@pytest.mark.parametrize("exchange", [e for e in _EXCHANGES.keys() if e not in [COINGECKO, EXX, WHALE_ALERT]])
def test_exchange_playback(exchange):
    dir = os.path.dirname(os.path.realpath(__file__))
    for pcap in glob.glob(f"{dir}/../../sample_data/{exchange}-*.0"):
        
        feed = _EXCHANGES[exchange]
        with open(pcap, 'r') as fp:
            header = fp.readline()
            sub = json.loads(header.split(": ", 1)[1])

        results = playback(feed(subscription=sub), pcap)
        message_count = get_message_count(pcap)

        assert results['messages_processed'] == message_count
        if isinstance(lookup_table[exchange], list):
            assert results['callbacks'] in lookup_table[exchange]
        else:
            assert lookup_table[exchange] == results['callbacks']
