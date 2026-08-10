'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import pytest

from cryptofeed.defines import BUY
from cryptofeed.types import Candle, Funding, OrderBook, Ticker, Trade


EXCHANGE = 'BENCH'
SYMBOL = 'BTC-USD'
PRICE = Decimal('65432.12345678')
AMOUNT = Decimal('0.15098765')
TIMESTAMP = 1786310525.123456

BIDS = {Decimal(65000 - i) / 100: Decimal(i + 1) / 1000 for i in range(100)}
ASKS = {Decimal(65100 + i) / 100: Decimal(i + 1) / 1000 for i in range(100)}


def test_trade_construct(benchmark):
    benchmark(lambda: Trade(EXCHANGE, SYMBOL, BUY, AMOUNT, PRICE, TIMESTAMP, id='1', type='market'))


def test_trade_to_dict(benchmark):
    trade = Trade(EXCHANGE, SYMBOL, BUY, AMOUNT, PRICE, TIMESTAMP, id='1', type='market')
    benchmark(lambda: trade.to_dict(numeric_type=str))


def test_trade_round_trip(benchmark):
    trade = Trade(EXCHANGE, SYMBOL, BUY, AMOUNT, PRICE, TIMESTAMP, id='1', type='market')
    as_dict = trade.to_dict(numeric_type=str)
    benchmark(lambda: Trade.from_dict(as_dict))


def test_ticker_construct(benchmark):
    benchmark(lambda: Ticker(EXCHANGE, SYMBOL, PRICE, PRICE, TIMESTAMP))


def test_candle_construct(benchmark):
    benchmark(lambda: Candle(EXCHANGE, SYMBOL, TIMESTAMP, TIMESTAMP + 60, '1m', None,
                             PRICE, PRICE, PRICE, PRICE, AMOUNT, True, TIMESTAMP))


def test_funding_construct(benchmark):
    benchmark(lambda: Funding(EXCHANGE, SYMBOL, PRICE, Decimal('0.0001'), TIMESTAMP + 3600,
                              TIMESTAMP, None))


def test_book_construct_100_levels(benchmark):
    benchmark(lambda: OrderBook(EXCHANGE, SYMBOL, bids=BIDS, asks=ASKS))


def test_book_to_dict_100_levels(benchmark):
    book = OrderBook(EXCHANGE, SYMBOL, bids=BIDS, asks=ASKS)
    book.timestamp = TIMESTAMP
    benchmark(lambda: book.to_dict(numeric_type=str))


@pytest.mark.parametrize('depth', [10, 100])
def test_book_to_dict_by_depth(benchmark, depth):
    bids = {Decimal(65000 - i) / 100: Decimal(i + 1) / 1000 for i in range(depth)}
    asks = {Decimal(65100 + i) / 100: Decimal(i + 1) / 1000 for i in range(depth)}
    book = OrderBook(EXCHANGE, SYMBOL, bids=bids, asks=asks)
    book.timestamp = TIMESTAMP
    benchmark(lambda: book.to_dict(numeric_type=str))
