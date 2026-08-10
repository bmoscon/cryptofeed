'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import aiohttp
import pytest

from cryptofeed.backends.quest import TradeQuest
from tests.backend.conftest import EXCHANGE, SYMBOL, require, run_backend, sample_trade


TABLE = f'trades-{EXCHANGE}'


async def query(sql: str, host: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'http://{host}:9000/exec', params={'query': sql}) as response:
            return await response.json()


@pytest.fixture
async def quest():
    host, _ = require('questdb')
    await query(f"DROP TABLE IF EXISTS '{TABLE}'", host)
    yield host
    await query(f"DROP TABLE IF EXISTS '{TABLE}'", host)


async def test_trade_round_trip(quest):
    backend = TradeQuest(host=quest)
    await run_backend(backend, [sample_trade(str(i)) for i in range(10)], settle=0.6)

    # ingestion is asynchronous on the server side
    for _ in range(20):
        result = await query(f"SELECT count() FROM '{TABLE}'", quest)
        if 'dataset' in result and result['dataset'] and result['dataset'][0][0] == 10:
            break
        await asyncio.sleep(0.5)

    assert 'dataset' in result, f'query failed: {result}'
    assert result['dataset'][0][0] == 10, f"expected 10 rows, got {result['dataset'][0][0]}"

    rows = await query(f"SELECT symbol, side, price, amount FROM '{TABLE}' LIMIT 1", quest)
    columns = [c['name'] for c in rows['columns']]
    record = dict(zip(columns, rows['dataset'][0]))
    assert record['symbol'] == SYMBOL
    assert record['side'] == 'buy'
    assert record['price'] == pytest.approx(65432.12345678901234)
