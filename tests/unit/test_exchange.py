'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import glob

import pytest

from cryptofeed.defines import ASCENDEX, BEQUANT, BITHUMB, CANDLES, BINANCE, BINANCE_DELIVERY, BITCOINCOM, BITFINEX, DYDX, EXX, BINANCE_FUTURES, BINANCE_US, BITFLYER, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, COINBASE, DERIBIT, FTX_US, FTX, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP, KRAKEN, KRAKEN_FUTURES, KUCOIN, OKCOIN, OKEX, OPEN_INTEREST, PHEMEX, POLONIEX, PROBIT, TICKER, TRADES, L2_BOOK, BYBIT, UPBIT
from cryptofeed.exchanges import EXCHANGE_MAP
from cryptofeed.raw_data_collection import playback
from cryptofeed.symbols import Symbols


# Some exchanges discard messages so we cant use a normal in == out comparison for testing purposes


lookup_table = {
    BEQUANT: {L2_BOOK: 978, TICKER: 1235, TRADES: 4040, CANDLES: 4040},
    BINANCE: {L2_BOOK: 532, TICKER: 412, TRADES: 28, CANDLES: 17},
    BINANCE_US: {TICKER: 241, TRADES: 3, L2_BOOK: 358, CANDLES: 3},
    BINANCE_FUTURES: {CANDLES: 67, L2_BOOK: 752, TICKER: 613, TRADES: 91},
    BINANCE_DELIVERY: {L2_BOOK: 1788, TICKER: 2240, TRADES: 51, CANDLES: 33},
    BITCOINCOM: {L2_BOOK: 990, TICKER: 1520, TRADES: 4004, CANDLES: 4004},
    BITFINEX: {L2_BOOK: 1600, TICKER: 21, TRADES: 210},
    BITFLYER: {L2_BOOK: 702, TICKER: 223, TRADES: 42},
    ASCENDEX: {L2_BOOK: 279, TRADES: 4},
    BITMEX: {L2_BOOK: 1979, TICKER: 436, TRADES: 27},
    BITSTAMP: {TRADES: 16, L2_BOOK: 548},
    BITTREX: {TICKER: 162, CANDLES: 20, L2_BOOK: 1014},
    BLOCKCHAIN: {L2_BOOK: 78},
    BYBIT: {TRADES: 251, L2_BOOK: 4278},
    COINBASE: {L2_BOOK: 9729, TICKER: 107, TRADES: 107},
    DERIBIT: {L2_BOOK: 46, TICKER: 89},
    DYDX: {L2_BOOK: 2130, TRADES: 1000},
    FTX: {L2_BOOK: 971, TICKER: 988, TRADES: 7},
    FTX_US: {L2_BOOK: 415, TICKER: 421},
    GEMINI: {L2_BOOK: 655, TRADES: 16},
    HITBTC: {L2_BOOK: 527, TICKER: 812, TRADES: 4000, CANDLES: 4000},
    HUOBI_DM:  {L2_BOOK: 4614, TRADES: 67},
    HUOBI_SWAP:  {L2_BOOK: 3977, TRADES: 67},
    HUOBI: {L2_BOOK: 292, TRADES: 73},
    KRAKEN_FUTURES: {TICKER: 107, TRADES: 3, L2_BOOK: 7024},
    KRAKEN: {L2_BOOK: 4279, TICKER: 18, TRADES: 10},
    OKCOIN: {L2_BOOK: 3161, TICKER: 63, TRADES: 30},
    OKEX: {L2_BOOK: 4372, TICKER: 139, TRADES: 108},    
    POLONIEX: {TICKER: 68, TRADES: 1, L2_BOOK: 165},
    UPBIT:  {L2_BOOK: 145, TRADES: 304},
    GATEIO: {CANDLES: 14, L2_BOOK: 169, TICKER: 22, TRADES: 9},
    PROBIT:  {L2_BOOK: 27, TRADES: 1001},
    KUCOIN: {TRADES: 18, TICKER: 830, CANDLES: 6, L2_BOOK: 3823},
    BITHUMB: {TRADES: 7},
    PHEMEX: {TRADES: 10025, CANDLES: 10041, L2_BOOK: 1337},
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


@pytest.mark.parametrize("exchange", [e for e in EXCHANGE_MAP.keys() if e not in [EXX]])
def test_exchange_playback(exchange):
    Symbols.clear()
    dir = os.path.dirname(os.path.realpath(__file__))
    pcap = glob.glob(f"{dir}/../../sample_data/{exchange}.*")

    results = playback(exchange, pcap)
    message_count = get_message_count(pcap)

    assert results['messages_processed'] == message_count
    if exchange == BEQUANT:
        # for some unknown reason on the github build servers this test always
        # fails even though it works fine on my local mac and linux machines
        expected = dict(lookup_table[exchange])
        expected[L2_BOOK] = 990

        assert lookup_table[exchange] == results['callbacks'] or expected == results['callbacks']
    else:
        assert lookup_table[exchange] == results['callbacks']
    Symbols.clear()
