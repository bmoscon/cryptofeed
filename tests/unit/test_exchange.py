'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

from cryptofeed.defines import *
from cryptofeed.capture import Replayer, playback
from cryptofeed.exchanges import EXCHANGE_MAP
from tests.util import CONFIG, ROOT, capture_path, read_metadata

import pytest


expected_counts = {
    BINANCE: {CANDLES: 50, L2_BOOK: 1438, TICKER: 14165, TRADES: 1068},
    BINANCE_DELIVERY: {CANDLES: 150, FUNDING: 3000, L2_BOOK: 35905, OPEN_INTEREST: 217, TICKER: 129938, TRADES: 2843},
    BINANCE_FUTURES: {CANDLES: 250, FUNDING: 5000, L2_BOOK: 1254, LIQUIDATIONS: 1, OPEN_INTEREST: 476, TICKER: 405520, TRADES: 36511},
    BINANCE_US: {CANDLES: 250, L2_BOOK: 40948, TICKER: 43882, TRADES: 235},
    BITFINEX: {L2_BOOK: 970453, L3_BOOK: 759457, TICKER: 943, TRADES: 3708},
    BITFLYER: {L2_BOOK: 9988, TICKER: 2637, TRADES: 1421},
    BITGET: {CANDLES: 30956, L1_BOOK: 126559, L2_BOOK: 109663, TICKER: 48514, TRADES: 17792},
    BITHUMB: {L1_BOOK: 54149, L2_BOOK: 54149, TICKER: 54149, TRADES: 3682},
    BITSTAMP: {L2_BOOK: 54803, L3_BOOK: 54882, TRADES: 1748},
    BYBIT: {CANDLES: 268, FUNDING: 47229, INDEX: 47229, L2_BOOK: 81553, OPEN_INTEREST: 47229, TICKER: 47229, TRADES: 40632},
    COINBASE: {CANDLES: 3619, L2_BOOK: 119991, TICKER: 32852, TRADES: 34176},
    CRYPTODOTCOM: {CANDLES: 15200, FUNDING: 78, INDEX: 3861, L2_BOOK: 29394, OPEN_INTEREST: 5889, TICKER: 24461, TRADES: 15887},
    DERIBIT: {FUNDING: 7835, L1_BOOK: 17894, L2_BOOK: 10071, OPEN_INTEREST: 5132, TICKER: 10388, TRADES: 530},
    DYDX: {L2_BOOK: 1415424, TRADES: 32},
    GATEIO: {CANDLES: 1626, L2_BOOK: 63537, TICKER: 7956, TRADES: 6504},
    GATEIO_FUTURES: {CANDLES: 3458, FUNDING: 5790, INDEX: 5790, L2_BOOK: 81679, OPEN_INTEREST: 5790, TICKER: 148269, TRADES: 38658},
    GEMINI: {L2_BOOK: 1186311, TRADES: 335},
    HTX: {CANDLES: 3842, L2_BOOK: 13986, TICKER: 46598, TRADES: 4229},
    HTX_SWAP: {FUNDING: 50, L2_BOOK: 72874, TRADES: 3592},
    HYPERLIQUID: {L1_BOOK: 66487, L2_BOOK: 2850, TRADES: 13932},
    INDEPENDENT_RESERVE: {L3_BOOK: 71878, TRADES: 8},
    KRAKEN: {CANDLES: 572, L2_BOOK: 491089, TICKER: 169, TRADES: 154},
    KRAKEN_FUTURES: {FUNDING: 34194, L2_BOOK: 1322586, OPEN_INTEREST: 1125, TICKER: 9392, TRADES: 6244},
    KUCOIN: {CANDLES: 3265, L2_BOOK: 344140, TICKER: 267701, TRADES: 10089},
    KUCOIN_FUTURES: {CANDLES: 3631, L2_BOOK: 446500, TICKER: 5182, TRADES: 7210},
    MEXC: {L1_BOOK: 149589, L2_BOOK: 66387, TRADES: 3052},
    OKX: {CANDLES: 2234, L2_BOOK: 54809, TICKER: 57725, TRADES: 1289},
    PHEMEX: {CANDLES: 51340, L2_BOOK: 59775, TRADES: 26638},
    POLONIEX: {L2_BOOK: 425719, TRADES: 17760},
    UPBIT: {L1_BOOK: 38981, L2_BOOK: 38981, TICKER: 38981, TRADES: 2588},
}


feed_overrides = {
    INDEPENDENT_RESERVE: {'request_limit': 1_000_000, 'SNAPSHOT_STALENESS_WAIT': 0},
}


def expected_message_count(exchange: str) -> int:
    count = 0
    for stream in read_metadata(exchange)['streams']:
        if stream['kind'] == 'ws':
            count += stream['messages']
        elif stream['address'] is not None:
            count += stream['requests']
    return count


@pytest.mark.playback
def test_no_missing_sample_data():
    for exchange in EXCHANGE_MAP:
        assert os.path.exists(capture_path(exchange)), f'{exchange} - missing captures in sample_data/'
        metadata = read_metadata(exchange)
        assert metadata['version'] == 1
        assert [entry['exchange'] for entry in metadata['feeds']] == [exchange]
        assert exchange in expected_counts
    assert set(expected_counts) == set(EXCHANGE_MAP)


@pytest.mark.playback
@pytest.mark.parametrize('exchange', sorted(EXCHANGE_MAP))
def test_exchange_playback(exchange):
    path = capture_path(exchange)
    feed = None
    if exchange in feed_overrides:
        feed = Replayer(path).build_feed(config=CONFIG)
        for attr, value in feed_overrides[exchange].items():
            setattr(feed, attr, value)

    results = playback(path, feed=feed, config=CONFIG, on_error='raise')

    assert results.messages_processed == expected_message_count(exchange)
    assert results.callbacks == expected_counts[exchange]
