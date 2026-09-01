'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncpg
import pytest

from cryptofeed.backends.postgres import BookPostgres, CandlesPostgres, FundingPostgres, IndexPostgres, LiquidationsPostgres, OpenInterestPostgres, TickerPostgres, TradePostgres
from tests.backend.conftest import assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

USER = 'cryptofeed'
PASSWORD = 'cryptofeed'
DB = 'cryptofeed'

COMMON = '"timestamp" TIMESTAMPTZ, "receipt_timestamp" TIMESTAMPTZ, "exchange" TEXT, "symbol" TEXT'

CASES = [
    (TradePostgres, 'trades', '"side" TEXT, "amount" NUMERIC, "price" NUMERIC, "trade_id" TEXT, "order_type" TEXT'),
    (TickerPostgres, 'ticker', '"bid" NUMERIC, "ask" NUMERIC'),
    (FundingPostgres, 'funding', '"mark_price" NUMERIC, "rate" NUMERIC, "next_funding_time" TIMESTAMPTZ, "predicted_rate" NUMERIC'),
    (OpenInterestPostgres, 'open_interest', '"open_interest" NUMERIC'),
    (IndexPostgres, 'index', '"price" NUMERIC'),
    (LiquidationsPostgres, 'liquidations', '"side" TEXT, "quantity" NUMERIC, "price" NUMERIC, "trade_id" TEXT, "status" TEXT'),
    (CandlesPostgres, 'candles', '"candle_start" TIMESTAMPTZ, "candle_stop" TIMESTAMPTZ, "interval" TEXT, "trades" INTEGER, "open" NUMERIC, "close" NUMERIC, "high" NUMERIC, "low" NUMERIC, "volume" NUMERIC, "closed" BOOLEAN'),
    (BookPostgres, 'book', '"data" JSONB'),
]


def table_name(backend_class) -> str:
    return f'test_{backend_class.__name__.lower()}'


@pytest.fixture
async def postgres():
    host, port = require('postgres')
    conn = await asyncpg.connect(host=host, port=port, user=USER, password=PASSWORD, database=DB)

    async def drop():
        for backend_class, _, _ in CASES:
            await conn.execute(f'DROP TABLE IF EXISTS {table_name(backend_class)}')

    await drop()
    for backend_class, _, columns in CASES:
        await conn.execute(f'CREATE TABLE {table_name(backend_class)} (id serial PRIMARY KEY, {COMMON}, {columns})')

    yield conn, host, port
    await drop()
    await conn.close()


@pytest.mark.parametrize('backend_class, kind, _columns', CASES, ids=[c.__name__ for c, _, _ in CASES])
async def test_write(postgres, backend_class, kind, _columns):
    conn, host, port = postgres
    data = samples(kind)
    table = table_name(backend_class)
    backend = backend_class(host=host, port=port, user=USER, pw=PASSWORD, db=DB, table=table)

    assert_written(await run_backend(backend, data), len(data))
    assert await conn.fetchval(f'SELECT count(*) FROM {table}') == len(data)


async def test_missing_table_is_reported(postgres):
    _, host, port = postgres
    backend = TradePostgres(host=host, port=port, user=USER, pw=PASSWORD, db=DB, table='no_such_table')

    with pytest.raises(ExceptionGroup) as info:
        await run_backend(backend, samples('trades', 1))
    assert 'does not exist' in str(info.value.exceptions[0])
