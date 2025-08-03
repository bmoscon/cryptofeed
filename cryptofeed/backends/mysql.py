'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from collections import defaultdict
from datetime import datetime as dt
from typing import Tuple, Any

import asyncmy
from asyncmy.cursors import DictCursor
from pymysql.err import IntegrityError
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, INDEX


LOG = logging.getLogger('feedhandler')


class MySQLCallback(BackendQueue):
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
            A dictionary which maps Cryptofeed's data type fields to MySQL's table column names, e.g. {'symbol': 'instrument', 'price': 'price', 'amount': 'size'}
            Can be a subset of Cryptofeed's available fields (see the cdefs listed under each data type in types.pyx). Can be listed any order.
            Note: to store BOOK data in a JSONB column, include a 'data' field, e.g. {'symbol': 'symbol', 'data': 'json_data'}
        """
        self.conn = None
        self.table = table if table else self.default_table
        self.custom_columns = custom_columns
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.user = user
        self.db = db
        self.pw = pw
        self.host = host
        self.port = port
        # Parse INSERT statement with user-specified column names
        # Performed at init to avoid repeated list joins
        self.placeholders = "(%s,%s,%s,%s,%s,%s)"
        self.insert_statement = f"INSERT INTO {self.table} ({','.join([v for v in self.custom_columns.values()])}) VALUES " if custom_columns else None
        self.running = True

    async def _connect(self):
        if self.conn is None:
            self.conn = await asyncmy.connect(user=self.user, password=self.pw, database=self.db, host=self.host, port=self.port)

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]
        self.placeholders = "(%s,%s,%s,%s,%s,%s)"
        return (None, timestamp, receipt_timestamp, feed, symbol, json.dumps(data))

    def _custom_format(self, data: Tuple):

        d = {
            **data[4],
            **{
                'exchange': data[0],
                'symbol': data[1],
                'timestamp': data[2],
                'receipt': data[3],
            }
        }
        self.placeholders = f"({','.join(['%s' for _ in self.custom_columns.keys()])})"

        # Cross-ref data dict with user column names from custom_columns dict, inserting None if requested data point not present
        def convert_value(value: Any) -> Any:
            if value is None:
                return value
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, dt):
                return value.strftime('%Y-%m-%d %H:%M:%S.%f')
            if isinstance(value, (int, float)):
                return str(value)
            return str(value)

        def prepare_data(data: dict, keys: list) -> tuple:
            return tuple(convert_value(data.get(key)) for key in keys)

        reuslt = prepare_data(d, self.custom_columns.keys())
        return reuslt

    async def writer(self):
        while self.running:
            async with self.read_queue() as updates:
                if len(updates) > 0:
                    batch = []
                    for data in updates:
                        ts = dt.utcfromtimestamp(data['timestamp']) if data['timestamp'] else None
                        rts = dt.utcfromtimestamp(data['receipt_timestamp'])
                        batch.append((data['exchange'], data['symbol'], ts, rts, data))
                    await self.write_batch(batch)

    async def write_batch(self, updates: list):
        await self._connect()
        values = [self.format(u) for u in updates]

        async with self.conn.cursor(cursor=DictCursor) as cursor:
            try:
                if self.custom_columns:
                    await cursor.executemany(self.insert_statement + self.placeholders, values)
                else:
                    await cursor.executemany(f"INSERT INTO {self.table} VALUES {self.placeholders}", values)

            except IntegrityError:
                # when restarting a subscription, some exchanges will re-publish a few messages
                pass
            except Exception:
                LOG.error(f'INSERT INTO {self.table}: ', exc_info=True)
            else:
                await cursor.commit()


class TradeMySQL(MySQLCallback, BackendCallback):
    default_table = TRADES

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            id = f"'{data['id']}'" if data['id'] else None
            otype = f"'{data['type']}'" if data['type'] else None
            return (None, f'{timestamp}', f'{receipt}', exchange, symbol, data['side'], data['amount'], data['price'], id, otype)


class FundingMySQL(MySQLCallback, BackendCallback):
    default_table = FUNDING

    def format(self, data: Tuple):
        if self.custom_columns:
            if data[4]['next_funding_time']:
                data[4]['next_funding_time'] = dt.utcfromtimestamp(data[4]['next_funding_time'])
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            ts = dt.utcfromtimestamp(data['next_funding_time']) if data['next_funding_time'] else None
            return (None, f'{timestamp}', f'{receipt}', exchange, symbol, data['mark_price'] if data['mark_price'] else None, data['rate'], f'{ts}', data['predicted_rate'])


class TickerMySQL(MySQLCallback, BackendCallback):
    default_table = TICKER

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            self.placeholders = f"({','.join(['%s' for _ in range(7)])})"
            exchange, symbol, timestamp, receipt, data = data
            return (None, f"{timestamp}", f"{receipt}", exchange, symbol, data['bid'], data['ask'])


class OpenInterestMySQL(MySQLCallback, BackendCallback):
    default_table = OPEN_INTEREST

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            self.placeholders = f"({','.join(['%s' for _ in range(6)])})"
            exchange, symbol, timestamp, receipt, data = data
            return (None, f'{timestamp}', f'{receipt}', exchange, symbol, data['open_interest'])


class IndexMySQL(MySQLCallback, BackendCallback):
    default_table = "market_" + INDEX

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            self.placeholders = f"({','.join(['%s' for _ in range(6)])})"
            exchange, symbol, timestamp, receipt, data = data
            return (None, f'{timestamp}', f'{receipt}', exchange, symbol, data['price'])


class LiquidationsMySQL(MySQLCallback, BackendCallback):
    default_table = LIQUIDATIONS

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            self.placeholders = f"({','.join(['%s' for _ in range(10)])})"
            exchange, symbol, timestamp, receipt, data = data
            return (None, f"{timestamp}", f"{receipt}", exchange, symbol, data['side'], data['quantity'], data['price'], data['id'], data['status'])


class BookMySQL(MySQLCallback, BackendBookCallback):
    default_table = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)

    def format(self, data: Tuple):
        if self.custom_columns:
            if 'book' in data[4]:
                data[4]['data'] = json.dumps({'snapshot': data[4]['book']})
            else:
                data[4]['data'] = json.dumps({'delta': data[4]['delta']})
            return self._custom_format(data)
        else:
            feed = data[0]
            symbol = data[1]
            timestamp = data[2]
            receipt_timestamp = data[3]
            data = data[4]
            if 'book' in data:
                data = {'snapshot': data['book']}
            else:
                data = {'delta': data['delta']}

            self.placeholders = f"({','.join(['%s' for _ in range(6)])})"
            return (None, f"{timestamp}", f"{receipt_timestamp}", feed, symbol, json.dumps(data))


class CandlesMySQL(MySQLCallback, BackendCallback):
    default_table = CANDLES

    def format(self, data: Tuple):
        if self.custom_columns:
            data[4]['start'] = dt.utcfromtimestamp(data[4]['start'])
            data[4]['stop'] = dt.utcfromtimestamp(data[4]['stop'])
            return self._custom_format(data)
        else:
            self.placeholders = f"({','.join(['%s' for _ in range(15)])})"
            exchange, symbol, timestamp, receipt, data = data

            open_ts = dt.utcfromtimestamp(data['start'])
            close_ts = dt.utcfromtimestamp(data['stop'])
            return (None, f"{timestamp}", f"{receipt}", exchange, symbol, open_ts, close_ts,
                    data['interval'],
                    data['trades'] if data['trades'] is not None else None,
                    data['open'], data['close'], data['high'], data['low'], data['volume'],
                    data['closed'] if data['closed'] else None)
