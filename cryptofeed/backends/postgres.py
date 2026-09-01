'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import re
from collections import defaultdict
from datetime import datetime as dt, timezone

import asyncpg
from cryptofeed import _json as json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue, PermanentWriteError
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, INDEX


_COMMON_FIELDS = frozenset({'exchange', 'symbol', 'timestamp', 'receipt_timestamp', 'receipt'})
_REJECTED = (asyncpg.exceptions.DataError, asyncpg.exceptions.IntegrityConstraintViolationError)


def _utc(timestamp: float):
    if timestamp is None:
        return None
    return f'{dt.fromtimestamp(timestamp, tz=timezone.utc):%Y-%m-%d %H:%M:%S.%f}+00'


def _render(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def _cast_type(base: str, modified: str) -> str:
    core = base[:-2] if base.endswith('[]') else base
    if core == 'character':
        return 'text' + base[len(core):]
    if core in ('bit', 'bit varying'):
        return modified
    return base


def _ident(data: dict) -> str:
    return f"exchange={data.get('exchange')!r} symbol={data.get('symbol')!r} timestamp={data.get('timestamp')!r}"


class PostgresCallback(BackendQueue):
    retryable_exceptions = (OSError, asyncpg.PostgresConnectionError)
    fields = frozenset()

    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, port=None, table=None, custom_columns: dict = None, none_to=None, numeric_type=float, **kwargs):
        """
        host: str
            Database host address
        user: str
            The name of the database role used for authentication.
        db: str
            The name of the database to connect to.
        pw: str
            Password to be used for authentication, if the server requires one.
        table: str
            Table name to insert into. Defaults to default_table that should be specified in child class
        custom_columns: dict
            A dictionary which maps Cryptofeed's data type fields to Postgres's table column names, e.g. {'symbol': 'instrument', 'price': 'price', 'amount': 'size'}
            Can be a subset of Cryptofeed's available fields (see the cdefs listed under each data type in types.pyx). Can be listed any order.
            Note: to store BOOK data in a JSONB column, include a 'data' field, e.g. {'symbol': 'symbol', 'data': 'json_data'}
            Both halves are checked when the backend first connects: an unknown column name
            or a field this callback never produces is an error, not a column of NULLs.
        """
        super().__init__(**kwargs)
        self.pool = None
        self.table = table if table else self.default_table
        self.custom_columns = custom_columns
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.user = user
        self.db = db
        self.pw = pw
        self.host = host
        self.port = port
        self._insert = None
        self._ncols = None

    async def connect(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(user=self.user, password=self.pw, database=self.db,
                                                  host=self.host, port=self.port, min_size=1, max_size=2)
        if self._insert is None:
            async with self.pool.acquire() as conn:
                await self._build_insert(conn)

    async def _build_insert(self, conn):
        qualified = await conn.fetchval('SELECT to_regclass($1)::text', self.table)
        if qualified is None:
            raise ValueError(f'table {self.table!r} does not exist - create it before starting the backend')

        rows = await conn.fetch(
            '''SELECT a.attname AS name, format_type(a.atttypid, NULL) AS base,
                      format_type(a.atttypid, a.atttypmod) AS modified,
                      (a.attidentity != '' OR pg_get_expr(d.adbin, d.adrelid) LIKE 'nextval(%') AS serial
               FROM pg_attribute a
               LEFT JOIN pg_attrdef d ON a.attrelid = d.adrelid AND a.attnum = d.adnum
               WHERE a.attrelid = to_regclass($1) AND a.attnum > 0 AND NOT a.attisdropped
               ORDER BY a.attnum''', self.table)
        if not rows:
            raise ValueError(f'table {self.table!r} exists but has no insertable columns')
        casts = {r['name']: _cast_type(r['base'], r['modified']) for r in rows}
        if self.custom_columns:
            self._check_custom_columns(casts)
            columns = list(self.custom_columns.values())
        else:
            columns = [r['name'] for r in rows if not r['serial']]
        column_list = ', '.join(f'"{c}"' for c in columns)
        cast_list = ', '.join(f'v{i}::{casts[c]}' for i, c in enumerate(columns, 1))
        arrays = ', '.join(f'${i}::text[]' for i in range(1, len(columns) + 1))
        names = ', '.join(f'v{i}' for i in range(1, len(columns) + 1))
        self._insert = (f'INSERT INTO {qualified} ({column_list}) SELECT {cast_list} '
                        f'FROM unnest({arrays}) AS u({names}) ON CONFLICT DO NOTHING')
        self._ncols = len(columns)

    def _check_custom_columns(self, casts: dict):
        missing = [c for c in self.custom_columns.values() if c not in casts]
        if missing:
            raise ValueError(f'custom_columns name columns missing from table {self.table!r}: {missing}')
        if self.fields:
            unknown = [f for f in self.custom_columns if f not in self.fields]
            if unknown:
                raise ValueError(f'custom_columns name fields {type(self).__name__} never produces: {unknown}. Valid fields: {sorted(self.fields)}')

    def _prepare(self, data: dict) -> dict:
        return data

    def _row(self, data: dict) -> tuple:
        data = self._prepare(data)
        ts = _utc(data['timestamp'])
        rts = _utc(data['receipt_timestamp'])
        if self.custom_columns:
            d = {**data, 'timestamp': ts, 'receipt': rts, 'receipt_timestamp': rts}
            return tuple(d.get(field) for field in self.custom_columns.keys())
        return self._default_row(data, ts, rts)

    def _default_row(self, data: dict, ts, rts) -> tuple:
        return (ts, rts, data['exchange'], data['symbol'], json.dumps(data))

    async def write_batch(self, batch: list):
        if not batch:
            return 0
        rows = [self._row(d) for d in batch]

        if len(rows[0]) != self._ncols:
            raise ValueError(f'table {self.table!r} has {self._ncols} insertable columns but {type(self).__name__} produces {len(rows[0])} values per row')
        arrays = [[_render(row[i]) for row in rows] for i in range(self._ncols)]

        try:
            async with self.pool.acquire() as conn:
                tag = await conn.execute(self._insert, *arrays)
        except _REJECTED as e:
            raise PermanentWriteError(self._rejection(batch, arrays, e)) from e

        return int(tag.rsplit(' ', 1)[-1])

    def _rejection(self, batch: list, arrays: list, exc) -> str:
        detail = str(exc).split('\n')[0]
        overlong = re.search(r'value too long for type [a-z ]+\((\d+)\)', detail)

        if overlong:
            limit = int(overlong.group(1))
            for column in arrays:
                for i, value in enumerate(column):
                    if value is not None and len(value) > limit:
                        return f'{self.table}: {detail} - row {_ident(batch[i])}'

        for value in re.findall(r'"([^"]*)"', detail):
            for column in arrays:
                if value in column:
                    return f'{self.table}: {detail} - row {_ident(batch[column.index(value)])}'

        if len(batch) == 1:
            return f'{self.table}: {detail} - row {_ident(batch[0])}'
        return (f'{self.table}: {detail} - batch of {len(batch)}, first {_ident(batch[0])}, last {_ident(batch[-1])}')

    async def close(self):
        if self.pool is not None:
            await self.pool.close()
            self.pool = None


class TradePostgres(PostgresCallback, BackendCallback):
    default_table = TRADES
    fields = _COMMON_FIELDS | {'side', 'amount', 'price', 'id', 'type'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['side'], data['amount'], data['price'], data['id'], data['type'])


class FundingPostgres(PostgresCallback, BackendCallback):
    default_table = FUNDING
    fields = _COMMON_FIELDS | {'mark_price', 'rate', 'next_funding_time', 'predicted_rate'}

    def _prepare(self, data):
        return {**data, 'next_funding_time': _utc(data['next_funding_time'])}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['mark_price'], data['rate'], data['next_funding_time'], data['predicted_rate'])


class TickerPostgres(PostgresCallback, BackendCallback):
    default_table = TICKER
    fields = _COMMON_FIELDS | {'bid', 'ask'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['bid'], data['ask'])


class OpenInterestPostgres(PostgresCallback, BackendCallback):
    default_table = OPEN_INTEREST
    fields = _COMMON_FIELDS | {'open_interest'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['open_interest'])


class IndexPostgres(PostgresCallback, BackendCallback):
    default_table = INDEX
    fields = _COMMON_FIELDS | {'price'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['price'])


class LiquidationsPostgres(PostgresCallback, BackendCallback):
    default_table = LIQUIDATIONS
    fields = _COMMON_FIELDS | {'side', 'quantity', 'price', 'id', 'status'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['side'], data['quantity'], data['price'], data['id'], data['status'])


class BookPostgres(PostgresCallback, BackendBookCallback):
    default_table = 'book'
    fields = _COMMON_FIELDS | {'data', 'book', 'delta'}

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)

    def _prepare(self, data):
        if 'book' in data:
            payload = json.dumps({'snapshot': data['book']})
        else:
            payload = json.dumps({'delta': data['delta']})
        return {**data, 'data': payload}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['data'])


class CandlesPostgres(PostgresCallback, BackendCallback):
    default_table = CANDLES
    fields = _COMMON_FIELDS | {'start', 'stop', 'interval', 'trades', 'open', 'close', 'high', 'low', 'volume', 'closed'}

    def _prepare(self, data):
        return {**data, 'start': _utc(data['start']), 'stop': _utc(data['stop'])}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['start'], data['stop'], data['interval'],
                data['trades'], data['open'], data['close'], data['high'], data['low'], data['volume'], data['closed'])
