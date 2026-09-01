'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest
from redis import asyncio as aioredis

from cryptofeed.backends.redis import *
from tests.backend.conftest import assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

PREFIX = 'cryptofeed-test'

CASES = [
    (TradeRedis, 'trades'),
    (TradeStream, 'trades'),
    (TickerRedis, 'ticker'),
    (TickerStream, 'ticker'),
    (FundingRedis, 'funding'),
    (FundingStream, 'funding'),
    (OpenInterestRedis, 'open_interest'),
    (OpenInterestStream, 'open_interest'),
    (LiquidationsRedis, 'liquidations'),
    (LiquidationsStream, 'liquidations'),
    (CandlesRedis, 'candles'),
    (CandlesStream, 'candles'),
    (BookRedis, 'book'),
    (BookStream, 'book'),
    (BookSnapshotRedisKey, 'book'),
]


@pytest.fixture
async def redis():
    host, port = require('redis')
    client = aioredis.from_url(f'redis://{host}:{port}')

    async def clear():
        async for key in client.scan_iter(match=f'{PREFIX}-*'):
            await client.delete(key)

    await clear()
    yield host, port
    await clear()
    await client.aclose()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(redis, backend_class, kind):
    host, port = redis
    data = samples(kind)
    backend = backend_class(host=host, port=port, key=f'{PREFIX}-{backend_class.__name__.lower()}')

    assert_written(await run_backend(backend, data), len(data))


async def test_data_lands_in_redis(redis):
    host, port = redis
    key = f'{PREFIX}-landed'
    data = samples('trades')
    backend = TradeRedis(host=host, port=port, key=key)

    assert_written(await run_backend(backend, data), len(data))

    client = aioredis.from_url(f'redis://{host}:{port}')
    try:
        assert await client.zcard(f'{key}-{data[0].exchange}-{data[0].symbol}') == len(data)
    finally:
        await client.aclose()
