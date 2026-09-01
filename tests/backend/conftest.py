'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import os
import socket
from decimal import Decimal

import pytest

from cryptofeed.backends.backend import BackendStats
from cryptofeed.defines import ASK, BID, BUY, FILLED, SELL
from cryptofeed.types import Candle, Funding, Index, Liquidation, OpenInterest, OrderBook, Ticker, Trade


EXCHANGE = 'TESTEX'
SYMBOL = 'BTC-USD'
TIMESTAMP = 1786310525.123456
RECEIPT = 1786310525.987654
PRICE = Decimal('65432.12')
AMOUNT = Decimal('0.15')


SERVICES = {
    'redis': ('REDIS_HOST', 'REDIS_PORT', '127.0.0.1', 6379),
    'postgres': ('POSTGRES_HOST', 'POSTGRES_PORT', '127.0.0.1', 5432),
    'mongo': ('MONGO_HOST', 'MONGO_PORT', '127.0.0.1', 27017),
    'kafka': ('KAFKA_HOST', 'KAFKA_PORT', '127.0.0.1', 9092),
    'influxdb': ('INFLUXDB_HOST', 'INFLUXDB_PORT', '127.0.0.1', 8086),
    'questdb': ('QUESTDB_HOST', 'QUESTDB_PORT', '127.0.0.1', 9000),
}


def require(name: str) -> tuple:
    host_var, port_var, host, port = SERVICES[name]
    host = os.environ.get(host_var, host)
    port = int(os.environ.get(port_var, port))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(2)

        if probe.connect_ex((host, port)) != 0:
            message = f'{name} is not reachable at {host}:{port}'

            if os.environ.get('BACKEND_SERVICES_REQUIRED'):
                pytest.fail(message)
            pytest.skip(f'{message} - see tests/backend/README.md')
    return host, port


def trades(n: int) -> list:
    return [Trade(EXCHANGE, SYMBOL, BUY if i % 2 else SELL, AMOUNT + i, PRICE + i, TIMESTAMP + i, id=str(i), type='limit') for i in range(n)]


def tickers(n: int) -> list:
    return [Ticker(EXCHANGE, SYMBOL, PRICE + i, PRICE + i + 1, TIMESTAMP + i) for i in range(n)]


def candles(n: int) -> list:
    return [Candle(EXCHANGE, SYMBOL, TIMESTAMP + i * 60, TIMESTAMP + (i + 1) * 60, '1m', i,
                   PRICE, PRICE + 1, PRICE + 2, PRICE - 1, AMOUNT, bool(i % 2), TIMESTAMP + i) for i in range(n)]


def funding(n: int) -> list:
    return [Funding(EXCHANGE, SYMBOL, PRICE + i, Decimal('0.0001'), TIMESTAMP + 28800, TIMESTAMP + i, predicted_rate=Decimal('0.0002')) for i in range(n)]


def open_interest(n: int) -> list:
    return [OpenInterest(EXCHANGE, SYMBOL, AMOUNT + i, TIMESTAMP + i) for i in range(n)]


def liquidations(n: int) -> list:
    return [Liquidation(EXCHANGE, SYMBOL, SELL, AMOUNT + i, PRICE + i, str(i), FILLED, TIMESTAMP + i) for i in range(n)]


def index(n: int) -> list:
    return [Index(EXCHANGE, SYMBOL, PRICE + i, TIMESTAMP + i) for i in range(n)]


def books(n: int) -> list:
    book = OrderBook(EXCHANGE, SYMBOL, bids={PRICE: AMOUNT, PRICE - 1: AMOUNT}, asks={PRICE + 1: AMOUNT, PRICE + 2: AMOUNT})
    book.timestamp = TIMESTAMP
    updates = [book]

    for i in range(1, n):
        delta = OrderBook(EXCHANGE, SYMBOL, bids=book.book.bids.to_dict(), asks=book.book.asks.to_dict())
        delta.book.bids[PRICE - 1] = AMOUNT + i
        delta.timestamp = TIMESTAMP + i
        delta.delta = {BID: [(PRICE - 1, AMOUNT + i)], ASK: []}
        updates.append(delta)
    return updates


SAMPLES = {
    'trades': trades,
    'ticker': tickers,
    'candles': candles,
    'funding': funding,
    'open_interest': open_interest,
    'liquidations': liquidations,
    'index': index,
    'book': books,
}


def samples(kind: str, n: int = 5) -> list:
    return SAMPLES[kind](n)


async def run_backend(backend, objects: list) -> BackendStats:
    async with asyncio.TaskGroup() as tg:
        backend.start_writer(tg, name=f'test.backend.{type(backend).__name__}')

        for i, obj in enumerate(objects):
            await backend(obj, RECEIPT + i)
        await backend.stop()

    return backend.stats


def assert_written(stats: BackendStats, expected: int):
    assert stats.last_error is None, f'backend recorded an error: {stats.last_error}'
    assert stats.dropped_overflow == 0, f'{stats.dropped_overflow} messages dropped by the queue'
    assert stats.dropped_failed == 0, f'{stats.dropped_failed} messages the backend could not write'
    assert stats.retries == 0, 'the backend had to retry a write'
    assert stats.conflicts == 0, f'{stats.conflicts} messages the backend considered duplicates'
    assert stats.written == expected, f'wrote {stats.written} of {expected} messages'
    assert stats.delivered == expected
    assert stats.batches >= 1, 'nothing was ever written'
    assert stats.qsize == 0, f'{stats.qsize} messages left in the queue'
    assert stats.last_write_ts is not None
