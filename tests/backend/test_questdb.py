'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import aiohttp
import pytest

from cryptofeed.backends.quest import BookQuest, CandlesQuest, FundingQuest, LiquidationsQuest, OpenInterestQuest, TickerQuest, TradeQuest
from tests.backend.conftest import EXCHANGE, assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

CASES = [
    (TradeQuest, 'trades'),
    (TickerQuest, 'ticker'),
    (FundingQuest, 'funding'),
    (OpenInterestQuest, 'open_interest'),
    (LiquidationsQuest, 'liquidations'),
    (CandlesQuest, 'candles'),
    (BookQuest, 'book'),
]


def key(backend_class) -> str:
    return f'test_{backend_class.__name__.lower()}'


def table(backend_class) -> str:
    return f'{key(backend_class)}-{EXCHANGE}'


async def execute(addr: str, query: str) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{addr}/exec', params={'query': query}) as response:
            return await response.json()


async def row_count(addr: str, name: str, expected: int, deadline: float = 30.0) -> int:
    result = {}
    try:
        async with asyncio.timeout(deadline):
            while True:
                result = await execute(addr, f"SELECT count() FROM '{name}'")
                if result.get('dataset', [[0]])[0][0] == expected:
                    return expected
                await asyncio.sleep(0.1)
    except TimeoutError:
        pytest.fail(f'questdb did not store the rows: {result}')


@pytest.fixture
async def quest():
    host, port = require('questdb')
    addr = f'http://{host}:{port}'

    async def drop():
        for backend_class, _ in CASES:
            await execute(addr, f"DROP TABLE IF EXISTS '{table(backend_class)}'")

    await drop()
    yield host, port, addr
    await drop()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(quest, backend_class, kind):
    host, port, addr = quest
    data = samples(kind)
    backend = backend_class(host=host, port=port, key=key(backend_class))

    assert_written(await run_backend(backend, data), len(data))

    assert await row_count(addr, table(backend_class), len(data)) == len(data)
