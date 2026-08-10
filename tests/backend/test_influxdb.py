'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import os

import aiohttp
import pytest

from cryptofeed.backends.influxdb import TradeInflux
from tests.backend.conftest import EXCHANGE, SYMBOL, require, run_backend, sample_trade


ORG = os.environ.get('INFLUXDB_ORG', 'cryptofeed')
BUCKET = os.environ.get('INFLUXDB_BUCKET', 'cryptofeed')
TOKEN = os.environ.get('INFLUXDB_TOKEN', 'cryptofeed-test-token')


async def flux(host: str, query: str):
    headers = {'Authorization': f'Token {TOKEN}', 'Content-Type': 'application/vnd.flux',
               'Accept': 'application/csv'}
    async with aiohttp.ClientSession() as session:
        async with session.post(f'http://{host}:8086/api/v2/query', params={'org': ORG},
                                data=query, headers=headers) as response:
            return await response.text()


@pytest.fixture
async def influx():
    host, port = require('influxdb')
    # the container needs its setup to have completed before it will accept writes
    for _ in range(30):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://{host}:{port}/health') as response:
                    if response.status == 200 and (await response.json()).get('status') == 'pass':
                        break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        pytest.skip('influxdb did not become healthy')
    yield host, port


async def test_trade_round_trip(influx):
    host, port = influx
    backend = TradeInflux(f'http://{host}:{port}', ORG, BUCKET, TOKEN, key='test_trades')
    await run_backend(backend, [sample_trade(str(i)) for i in range(5)], settle=0.8)

    measurement = f'test_trades-{EXCHANGE}'
    query = f'''
    from(bucket: "{BUCKET}")
      |> range(start: -5y, stop: 5y)
      |> filter(fn: (r) => r._measurement == "{measurement}")
    '''
    for _ in range(15):
        body = await flux(host, query)
        if SYMBOL in body:
            break
        await asyncio.sleep(0.5)

    assert SYMBOL in body, f'no trade data came back from influx: {body[:400]}'
    assert EXCHANGE in body
