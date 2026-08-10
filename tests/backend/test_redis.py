'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json

import pytest

from cryptofeed.backends.redis import TradeRedis, TradeStream
from tests.backend.conftest import AMOUNT, EXCHANGE, PRICE, SYMBOL, assert_exact, require, run_backend, sample_trade


@pytest.fixture
def redis_client():
    redis = pytest.importorskip('redis.asyncio')
    host, port = require('redis')
    client = redis.Redis(host=host, port=port, decode_responses=True)
    yield client


async def test_zset_round_trip(redis_client):
    key = 'test-trades-zset'
    await redis_client.delete(f'{key}-{EXCHANGE}-{SYMBOL}')

    backend = TradeRedis(host=await _host(redis_client), port=await _port(redis_client), key=key, numeric_type=str)
    await run_backend(backend, [sample_trade()])

    entries = await redis_client.zrange(f'{key}-{EXCHANGE}-{SYMBOL}', 0, -1)
    assert len(entries) == 1, f'expected one entry, got {entries}'
    payload = json.loads(entries[0])
    assert payload['exchange'] == EXCHANGE
    assert payload['symbol'] == SYMBOL
    assert_exact(payload['price'], PRICE, 'price')
    assert_exact(payload['amount'], AMOUNT, 'amount')
    await redis_client.delete(f'{key}-{EXCHANGE}-{SYMBOL}')


async def test_stream_round_trip(redis_client):
    key = 'test-trades-stream'
    stream = f'{key}-{EXCHANGE}-{SYMBOL}'
    await redis_client.delete(stream)

    backend = TradeStream(host=await _host(redis_client), port=await _port(redis_client), key=key, numeric_type=str)
    await run_backend(backend, [sample_trade(str(i)) for i in range(5)])

    entries = await redis_client.xrange(stream)
    assert len(entries) == 5, f'expected five entries, got {len(entries)}'
    ids = [fields['id'] for _, fields in entries]
    assert ids == [str(i) for i in range(5)], 'stream lost ordering or messages'
    assert_exact(entries[0][1]['price'], PRICE, 'price')
    await redis_client.delete(stream)


async def _host(client):
    return client.connection_pool.connection_kwargs['host']


async def _port(client):
    return client.connection_pool.connection_kwargs['port']
