'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import pytest
from order_book import OrderBook as RawBook

from cryptofeed.types import OrderBook


EXCHANGE = 'BENCH'
SYMBOL = 'BTC-USD'
LEVELS = 200


def make_bids(count=LEVELS):
    return {Decimal(65000 - i) / 100: Decimal(i + 1) / 1000 for i in range(count)}


def make_asks(count=LEVELS):
    return {Decimal(65100 + i) / 100: Decimal(i + 1) / 1000 for i in range(count)}


def test_single_level_update(benchmark):
    book = OrderBook(EXCHANGE, SYMBOL, bids=make_bids(), asks=make_asks())
    price = Decimal('650.005')
    size = Decimal('1.5')

    def update():
        book.book.bids[price] = size

    benchmark(update)


def test_level_delete(benchmark):
    book = OrderBook(EXCHANGE, SYMBOL, bids=make_bids(), asks=make_asks())
    price = Decimal('650.00')

    def churn():
        book.book.bids[price] = Decimal('1.0')
        del book.book.bids[price]

    benchmark(churn)


def test_top_of_book_read(benchmark):
    book = OrderBook(EXCHANGE, SYMBOL, bids=make_bids(), asks=make_asks())
    benchmark(lambda: (book.book.bids.index(0), book.book.asks.index(0)))


@pytest.mark.parametrize('checksum_format', ['KRAKEN', 'OKX'])
def test_checksum(benchmark, checksum_format):
    book = RawBook(checksum_format=checksum_format)
    for price, size in make_bids().items():
        book.bids[price] = size
    for price, size in make_asks().items():
        book.asks[price] = size
    benchmark(book.checksum)


def test_full_book_replace(benchmark):
    book = OrderBook(EXCHANGE, SYMBOL)
    bids, asks = make_bids(), make_asks()

    def replace():
        book.book.bids = bids
        book.book.asks = asks

    benchmark(replace)
