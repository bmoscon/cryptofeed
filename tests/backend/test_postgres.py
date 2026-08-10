'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.backends.postgres import TradePostgres
from tests.backend.conftest import AMOUNT, EXCHANGE, PRICE, SYMBOL, assert_exact, require, run_backend, sample_trade


TABLE = 'test_trades'
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id serial PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    side VARCHAR(8),
    amount NUMERIC(64, 32),
    price NUMERIC(64, 32),
    trade_id VARCHAR(64),
    order_type VARCHAR(32)
)
"""


@pytest.fixture
async def pg():
    asyncpg = pytest.importorskip('asyncpg')
    host, port = require('postgres')
    conn = await asyncpg.connect(host=host, port=port, user='cryptofeed', password='cryptofeed', database='cryptofeed')
    await conn.execute(f'DROP TABLE IF EXISTS {TABLE}')
    await conn.execute(SCHEMA)
    yield conn, host, port
    await conn.execute(f'DROP TABLE IF EXISTS {TABLE}')
    await conn.close()


async def test_trade_round_trip(pg):
    conn, host, port = pg
    backend = TradePostgres(host=host, port=port, user='cryptofeed', pw='cryptofeed',
                            db='cryptofeed', table=TABLE, numeric_type=str)
    await run_backend(backend, [sample_trade('abc123')])

    rows = await conn.fetch(f'SELECT * FROM {TABLE}')
    assert len(rows) == 1, f'expected one row, got {len(rows)}'
    row = rows[0]
    assert row['exchange'] == EXCHANGE
    assert row['symbol'] == SYMBOL
    assert row['trade_id'] == 'abc123'
    assert_exact(row['price'], PRICE, 'price')
    assert_exact(row['amount'], AMOUNT, 'amount')


async def test_every_trade_is_inserted(pg):
    conn, host, port = pg
    backend = TradePostgres(host=host, port=port, user='cryptofeed', pw='cryptofeed',
                            db='cryptofeed', table=TABLE, numeric_type=str)
    await run_backend(backend, [sample_trade(str(i)) for i in range(100)], settle=0.8)

    count = await conn.fetchval(f'SELECT count(*) FROM {TABLE}')
    assert count == 100, f'expected 100 rows, got {count}'
    ids = [r['trade_id'] for r in await conn.fetch(f'SELECT trade_id FROM {TABLE} ORDER BY id')]
    assert ids == [str(i) for i in range(100)], 'rows were reordered or lost'
