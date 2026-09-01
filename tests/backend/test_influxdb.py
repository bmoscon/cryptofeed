'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import os

import aiohttp
import pytest

from cryptofeed.backends.influxdb import BookInflux, CandlesInflux, FundingInflux, LiquidationsInflux, OpenInterestInflux, TickerInflux, TradeInflux
from tests.backend.conftest import assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

ORG = os.environ.get('INFLUXDB_ORG', 'cryptofeed')
BUCKET = os.environ.get('INFLUXDB_BUCKET', 'cryptofeed')
TOKEN = os.environ.get('INFLUXDB_TOKEN', 'cryptofeed-test-token')

CASES = [
    (TradeInflux, 'trades'),
    (TickerInflux, 'ticker'),
    (FundingInflux, 'funding'),
    (OpenInterestInflux, 'open_interest'),
    (LiquidationsInflux, 'liquidations'),
    (CandlesInflux, 'candles'),
    (BookInflux, 'book'),
]


@pytest.fixture
async def influx():
    host, port = require('influxdb')
    addr = f'http://{host}:{port}'

    async with aiohttp.ClientSession() as session:
        for _ in range(60):
            try:
                async with session.get(f'{addr}/health') as response:
                    if response.status == 200 and (await response.json()).get('status') == 'pass':
                        break
            except aiohttp.ClientError:
                pass
            await asyncio.sleep(1)
        else:
            pytest.fail(f'influxdb at {addr} never reported healthy')
    yield addr


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(influx, backend_class, kind):
    data = samples(kind)
    backend = backend_class(influx, ORG, BUCKET, TOKEN, key=f'test_{backend_class.__name__.lower()}')

    assert_written(await run_backend(backend, data), len(data))


async def test_bad_token_is_not_retried(influx):
    data = samples('trades')
    backend = TradeInflux(influx, ORG, BUCKET, 'not-a-real-token', key='test_unauthorized')

    stats = await run_backend(backend, data)
    assert stats.dropped_failed == len(data)
    assert stats.written == 0
    assert stats.retries == 0
    assert stats.last_error is not None
