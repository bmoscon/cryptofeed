'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime, timezone

import clickhouse_connect
import pytest

from cryptofeed.backends.backend import RetryPolicy
from cryptofeed.backends.clickhouse import BookClickHouse, CandlesClickHouse, FundingClickHouse, IndexClickHouse, LiquidationsClickHouse, OpenInterestClickHouse, TickerClickHouse, TradeClickHouse
from tests.backend.conftest import EXCHANGE, PRICE, SYMBOL, TIMESTAMP, assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

USER = 'cryptofeed'
PASSWORD = 'cryptofeed'
DB = 'cryptofeed'

CASES = [(TradeClickHouse, 'trades'), (TickerClickHouse, 'ticker'), (FundingClickHouse, 'funding'), (OpenInterestClickHouse, 'open_interest'),
         (IndexClickHouse, 'index'), (LiquidationsClickHouse, 'liquidations'), (CandlesClickHouse, 'candles'), (BookClickHouse, 'book')]

REJECTED = '''CREATE TABLE test_rejected (timestamp DateTime64(6, 'UTC'), receipt_timestamp DateTime64(6, 'UTC'), exchange String, symbol String,
              side String, amount Decimal(38, 18), price Decimal(38, 18), trade_id Nullable(String), order_type Nullable(String),
              CONSTRAINT never CHECK price < 0) ENGINE = MergeTree ORDER BY timestamp'''
UNSERIALIZABLE = '''CREATE TABLE test_unserializable (timestamp DateTime64(6, 'UTC'), receipt_timestamp DateTime64(6, 'UTC'), exchange String, symbol String,
                    side String, amount Decimal(38, 18), price UInt8, trade_id Nullable(String), order_type Nullable(String)) ENGINE = MergeTree ORDER BY timestamp'''
EXTRA_TABLES = ('test_rejected', 'test_unserializable')


def table_name(backend_class) -> str:
    return f'test_{backend_class.__name__.lower()}'


def backend(backend_class, host, port, table, **kwargs):
    return backend_class(host=host, port=port, user=USER, pw=PASSWORD, db=DB, table=table, **kwargs)


async def count(client, table: str) -> int:
    return int(await client.command(f'SELECT count() FROM {table}'))


@pytest.fixture
async def clickhouse():
    host, port = require('clickhouse')
    client = await clickhouse_connect.get_async_client(host=host, port=port, username=USER, password=PASSWORD, database=DB)

    async def drop():
        for table in [table_name(backend_class) for backend_class, _ in CASES] + list(EXTRA_TABLES):
            await client.command(f'DROP TABLE IF EXISTS {table}')

    await drop()
    for backend_class, _ in CASES:
        await client.command(backend_class.create_table_sql(table_name(backend_class)))

    yield client, host, port
    await drop()
    await client.close()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(clickhouse, backend_class, kind):
    client, host, port = clickhouse
    data = samples(kind)
    table = table_name(backend_class)

    assert_written(await run_backend(backend(backend_class, host, port, table), data), len(data))
    assert await count(client, table) == len(data)


async def test_values_round_trip(clickhouse):
    client, host, port = clickhouse
    table = table_name(TradeClickHouse)
    data = samples('trades', 1)

    assert_written(await run_backend(backend(TradeClickHouse, host, port, table), data), 1)
    result = await client.query(f'SELECT timestamp, exchange, symbol, side, amount, price, trade_id, order_type FROM {table}')
    timestamp, exchange, symbol, side, amount, price, trade_id, order_type = result.first_row

    # the driver reads DateTime64 back as naive UTC by default
    assert timestamp.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(TIMESTAMP, tz=timezone.utc)
    assert (exchange, symbol, side, trade_id, order_type) == (EXCHANGE, SYMBOL, data[0].side, '0', 'limit')
    assert price == PRICE
    assert amount == data[0].amount


async def test_custom_columns(clickhouse):
    client, host, port = clickhouse
    await client.command("CREATE TABLE test_custom (ts DateTime64(6, 'UTC'), instrument String, px Decimal(38, 18), note String DEFAULT 'none') ENGINE = MergeTree ORDER BY ts")
    data = samples('trades', 3)
    try:
        columns = {'timestamp': 'ts', 'symbol': 'instrument', 'price': 'px'}
        assert_written(await run_backend(backend(TradeClickHouse, host, port, 'test_custom', custom_columns=columns), data), len(data))
        assert await client.command('SELECT count() FROM test_custom WHERE note = \'none\' AND instrument = {symbol:String}', parameters={'symbol': SYMBOL}) == len(data)

        with pytest.raises(ExceptionGroup) as info:
            await run_backend(backend(TradeClickHouse, host, port, 'test_custom', custom_columns={'price': 'no_such_column'}), data)
        assert 'no_such_column' in str(info.value.exceptions[0])

        with pytest.raises(ExceptionGroup) as info:
            await run_backend(backend(TradeClickHouse, host, port, 'test_custom', custom_columns={'volume': 'px'}), data)
        assert 'never produces' in str(info.value.exceptions[0])
    finally:
        await client.command('DROP TABLE IF EXISTS test_custom')


async def test_missing_table_is_reported(clickhouse):
    _, host, port = clickhouse

    with pytest.raises(ExceptionGroup) as info:
        await run_backend(backend(TradeClickHouse, host, port, 'no_such_table'), samples('trades', 1))
    assert 'does not exist' in str(info.value.exceptions[0])


async def test_server_rejection_is_dropped_not_retried(clickhouse):
    client, host, port = clickhouse
    await client.command(REJECTED)
    data = samples('trades')

    stats = await run_backend(backend(TradeClickHouse, host, port, 'test_rejected'), data)
    assert stats.dropped_failed == len(data)
    assert stats.written == 0
    assert stats.retries == 0
    assert 'VIOLATED_CONSTRAINT' in stats.last_error
    assert await count(client, 'test_rejected') == 0


async def test_unserializable_row_is_dropped_not_retried(clickhouse):
    client, host, port = clickhouse
    await client.command(UNSERIALIZABLE)
    data = samples('trades')

    stats = await run_backend(backend(TradeClickHouse, host, port, 'test_unserializable'), data)
    assert stats.dropped_failed == len(data)
    assert stats.written == 0
    assert stats.retries == 0
    assert await count(client, 'test_unserializable') == 0


async def test_unreachable_server_is_retried(clickhouse):
    _, host, _ = clickhouse
    data = samples('trades')
    retry = RetryPolicy(max_attempts=2, base=0.01, jitter=False)

    stats = await run_backend(backend(TradeClickHouse, host, 1, table_name(TradeClickHouse), retry=retry), data)
    assert stats.retries == 1
    assert stats.dropped_failed == len(data)
    assert stats.written == 0
    assert 'OperationalError' in stats.last_error
