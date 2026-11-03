'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import struct
from collections import defaultdict
from datetime import datetime as dt, timezone
from decimal import Decimal

import clickhouse_connect
from clickhouse_connect.driver.exceptions import DatabaseError, DataError, OperationalError, ProgrammingError

from cryptofeed import _json as json
from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue, PermanentWriteError
from cryptofeed.defines import CANDLES, FUNDING, INDEX, LIQUIDATIONS, OPEN_INTEREST, TICKER, TRADES


_COMMON_FIELDS = frozenset({'exchange', 'symbol', 'timestamp', 'receipt_timestamp', 'receipt'})
_COMMON_COLUMNS = (('timestamp', "DateTime64(6, 'UTC')"), ('receipt_timestamp', "DateTime64(6, 'UTC')"), ('exchange', 'LowCardinality(String)'), ('symbol', 'LowCardinality(String)'))
_NUMERIC = 'Decimal(38, 18)'
_NOT_INSERTABLE = frozenset({'MATERIALIZED', 'ALIAS'})
_UNSERIALIZABLE = (TypeError, ValueError, ArithmeticError, AttributeError, struct.error)
_TRANSIENT = frozenset({
    159,   # TIMEOUT_EXCEEDED
    164,   # READONLY
    173,   # CANNOT_ALLOCATE_MEMORY
    201,   # QUOTA_EXCEEDED
    202,   # TOO_MANY_SIMULTANEOUS_QUERIES
    203,   # NO_FREE_CONNECTION
    209,   # SOCKET_TIMEOUT
    210,   # NETWORK_ERROR
    236,   # ABORTED
    241,   # MEMORY_LIMIT_EXCEEDED
    242,   # TABLE_IS_READ_ONLY
    243,   # NOT_ENOUGH_SPACE
    252,   # TOO_MANY_PARTS
    279,   # ALL_CONNECTION_TRIES_FAILED
    319,   # UNKNOWN_STATUS_OF_INSERT
    394,   # QUERY_WAS_CANCELLED
    425,   # SYSTEM_ERROR
    439,   # CANNOT_SCHEDULE_TASK
    999,   # KEEPER_EXCEPTION
    1000,  # POCO_EXCEPTION
    1001,  # STD_EXCEPTION
    1002,  # UNKNOWN_EXCEPTION
})


def _utc(timestamp: float):
    if timestamp is None:
        return None
    return dt.fromtimestamp(timestamp, tz=timezone.utc)


def _ident(data: dict) -> str:
    return f"exchange={data.get('exchange')!r} symbol={data.get('symbol')!r} timestamp={data.get('timestamp')!r}"


class ClickHouseCallback(BackendQueue):
    retryable_exceptions = (OperationalError, OSError, TimeoutError)
    fields = frozenset()
    COLUMNS = (('data', 'String'),)
    ENGINE = 'MergeTree PARTITION BY toYYYYMM(timestamp) ORDER BY (exchange, symbol, timestamp)'
    MAX_ERROR = 500

    @classmethod
    def create_table_sql(cls, table: str = None, engine: str = None) -> str:
        columns = ', '.join(f'`{name}` {ch_type}' for name, ch_type in _COMMON_COLUMNS + cls.COLUMNS)
        return f'CREATE TABLE IF NOT EXISTS {table or cls.default_table} ({columns}) ENGINE = {engine or cls.ENGINE}'

    def __init__(self, host=None, user=None, pw=None, db=None, port=None, table=None, secure=False, custom_columns: dict = None, none_to=None, numeric_type=Decimal, client_options: dict = None, **kwargs):
        """
        host: str
            ClickHouse host address. Defaults to localhost
        user: str
            The name of the ClickHouse user used for authentication. Defaults to the server's default user
        pw: str
            Password to be used for authentication, if the server requires one.
        db: str
            The database holding the table. Defaults to the user's default database
        port: int
            The HTTP(S) port. Defaults to 8123, or 8443 when secure is True
        table: str
            Table name to insert into, optionally qualified as db.table. Defaults to default_table that should be specified in child class
        secure: bool
            Connect over HTTPS/TLS (ClickHouse Cloud needs this)
        custom_columns: dict
            A dictionary which maps Cryptofeed's data type fields to the table's column names, e.g. {'symbol': 'instrument', 'price': 'price', 'amount': 'size'}
            Can be a subset of Cryptofeed's available fields (see the cdefs listed under each data type in types.pyx). Can be listed any order.
            Note: to store BOOK data in a String column, include a 'data' field, e.g. {'symbol': 'symbol', 'data': 'json_data'}
            Both halves are checked when the backend first connects: an unknown column name
            or a field this callback never produces is an error, not a column of empty values.
        none_to: any
            if not None, convert None values to this value before inserting. A None can only be written to a Nullable column
        numeric_type: type
            cast numerics to this value. Decimal (default) for Decimal columns, float for Float64 columns
        client_options: dict
            passed straight to clickhouse_connect.get_async_client - compress, settings (e.g. {'async_insert': 1}),
            connect_timeout, send_receive_timeout, dsn, access_token and anything else the driver accepts.
            send_receive_timeout defaults to 30 seconds here rather than the driver's 300, so a stalled
            server is retried instead of blocking the writer; an option given here is left alone.
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.pw = pw
        self.db = db
        self.secure = secure
        self.table = table if table else self.default_table
        self.custom_columns = custom_columns
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.client_options = {'client_name': 'cryptofeed', 'send_receive_timeout': 30, **(client_options or {})}
        self.client = None
        self._context = None

    async def connect(self):
        if self.client is None:
            self.client = await clickhouse_connect.get_async_client(host=self.host, port=self.port, username=self.user, password=self.pw or '', database=self.db, secure=self.secure, **self.client_options)

        if self._context is None:
            await self._build_insert()

    async def _build_insert(self):
        database, _, name = self.table.rpartition('.')
        result = await self.client.query(
            '''SELECT name, type, default_kind FROM system.columns
               WHERE database = if(empty({database:String}), currentDatabase(), {database:String}) AND table = {table:String}
               ORDER BY position''', parameters={'database': database, 'table': name})
        rows = result.result_rows
        if not rows:
            raise ValueError(f'table {self.table!r} does not exist - create it before starting the backend')

        types = {name: ch_type for name, ch_type, _ in rows}
        if self.custom_columns:
            self._check_custom_columns(types)
            columns = list(self.custom_columns.values())
        else:
            columns = [name for name, _, kind in rows if kind not in _NOT_INSERTABLE]

        if not columns:
            raise ValueError(f'table {self.table!r} exists but has no insertable columns')

        self._context = await self.client.create_insert_context(self.table, columns, column_type_names=[types[c] for c in columns])

    def _check_custom_columns(self, types: dict):
        missing = [c for c in self.custom_columns.values() if c not in types]

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
        columns = self._context.column_names

        if len(rows[0]) != len(columns):
            raise ValueError(f'table {self.table!r} has {len(columns)} insertable columns but {type(self).__name__} produces {len(rows[0])} values per row')

        try:
            await self.client.insert(context=self._context, data=rows)
        except (OperationalError, ProgrammingError):
            raise
        except DataError as e:
            raise PermanentWriteError(self._rejection(batch, e)) from e
        except DatabaseError as e:
            code = getattr(e, 'code', None)
            if code is None or code in _TRANSIENT:
                # no code means the reply did not come from ClickHouse itself (a proxy or load balancer)
                raise OperationalError(str(e), code=code, name=getattr(e, 'name', None)) from e
            raise PermanentWriteError(self._rejection(batch, e)) from e
        except _UNSERIALIZABLE as e:
            raise PermanentWriteError(self._rejection(batch, e)) from e

    def _rejection(self, batch: list, exc) -> str:
        detail = str(exc).split('\n')[0][:self.MAX_ERROR]
        if len(batch) == 1:
            return f'{self.table}: {detail} - row {_ident(batch[0])}'

        return f'{self.table}: {detail} - batch of {len(batch)}, first {_ident(batch[0])}, last {_ident(batch[-1])}'

    async def close(self):
        if self.client is not None:
            await self.client.close()
            self.client = None
            self._context = None


class TradeClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRADES
    COLUMNS = (('side', 'LowCardinality(String)'), ('amount', _NUMERIC), ('price', _NUMERIC), ('trade_id', 'Nullable(String)'), ('order_type', 'LowCardinality(Nullable(String))'))
    fields = _COMMON_FIELDS | {'side', 'amount', 'price', 'id', 'type'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['side'], data['amount'], data['price'], data['id'], data['type'])


class FundingClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FUNDING
    COLUMNS = (('mark_price', f'Nullable({_NUMERIC})'), ('rate', f'Nullable({_NUMERIC})'), ('next_funding_time', "Nullable(DateTime64(6, 'UTC'))"), ('predicted_rate', f'Nullable({_NUMERIC})'))
    fields = _COMMON_FIELDS | {'mark_price', 'rate', 'next_funding_time', 'predicted_rate'}

    def _prepare(self, data):
        return {**data, 'next_funding_time': _utc(data['next_funding_time'])}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['mark_price'], data['rate'], data['next_funding_time'], data['predicted_rate'])


class TickerClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TICKER
    COLUMNS = (('bid', _NUMERIC), ('ask', _NUMERIC))
    fields = _COMMON_FIELDS | {'bid', 'ask'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['bid'], data['ask'])


class OpenInterestClickHouse(ClickHouseCallback, BackendCallback):
    default_table = OPEN_INTEREST
    COLUMNS = (('open_interest', _NUMERIC),)
    fields = _COMMON_FIELDS | {'open_interest'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['open_interest'])


class IndexClickHouse(ClickHouseCallback, BackendCallback):
    default_table = INDEX
    COLUMNS = (('price', _NUMERIC),)
    fields = _COMMON_FIELDS | {'price'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['price'])


class LiquidationsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = LIQUIDATIONS
    COLUMNS = (('side', 'LowCardinality(String)'), ('quantity', _NUMERIC), ('price', _NUMERIC), ('trade_id', 'Nullable(String)'), ('status', 'LowCardinality(Nullable(String))'))
    fields = _COMMON_FIELDS | {'side', 'quantity', 'price', 'id', 'status'}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['side'], data['quantity'], data['price'], data['id'], data['status'])


class BookClickHouse(ClickHouseCallback, BackendBookCallback):
    default_table = 'book'
    COLUMNS = (('data', 'String'),)
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


class CandlesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = CANDLES
    COLUMNS = (('candle_start', "DateTime64(6, 'UTC')"), ('candle_stop', "DateTime64(6, 'UTC')"), ('interval', 'LowCardinality(String)'), ('trades', 'Nullable(UInt32)'),
               ('open', _NUMERIC), ('close', _NUMERIC), ('high', _NUMERIC), ('low', _NUMERIC), ('volume', _NUMERIC), ('closed', 'Bool'))
    fields = _COMMON_FIELDS | {'start', 'stop', 'interval', 'trades', 'open', 'close', 'high', 'low', 'volume', 'closed'}

    def _prepare(self, data):
        return {**data, 'start': _utc(data['start']), 'stop': _utc(data['stop'])}

    def _default_row(self, data, ts, rts):
        return (ts, rts, data['exchange'], data['symbol'], data['start'], data['stop'], data['interval'],
                data['trades'], data['open'], data['close'], data['high'], data['low'], data['volume'], data['closed'])
