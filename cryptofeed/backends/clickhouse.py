'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from datetime import datetime as dt
import time
from typing import Tuple
import uuid
from aioch import Client
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, INDEX


class ClickHouseCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, port=None, table=None, custom_columns: dict = None, none_to=None, numeric_type=float, **kwargs):
        """
        host: str
            Database host address
        user: str
            The name of the database role used for authentication, defaults to 'default'.
        db: str
            The name of the database to connect to.
        pw: str
            Password to be used for authentication, if the server requires one.
        table: str
            Table name to insert into. Defaults to default_table that should be specified in child class
        custom_columns: dict
            A dictionary which maps Cryptofeed's data type fields to ClickHouse's table column names, e.g. {'symbol': 'instrument', 'price': 'price', 'amount': 'size'}
            Can be a subset of Cryptofeed's available fields (see the cdefs listed under each data type in types.pyx). Can be listed any order.
            Note: to store BOOK data in a JSONB column, include a 'data' field, e.g. {'symbol': 'symbol', 'data': 'json_data'}
        """
        self.conn = None
        self.table = table if table else self.default_table
        self.custom_columns = custom_columns
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.user = user if user else 'default'
        self.db = db if db else ''
        self.pw = pw if pw else ''
        self.host = host
        self.port = port if port else 9000
        # Parse INSERT statement with user-specified column names
        # Performed at init to avoid repeated list joins
        self.insert_statement = f"INSERT INTO {self.table} (id, {','.join([v for v in self.custom_columns.values()])}) VALUES " if custom_columns else None
        self.running = True

    async def _connect(self):
        if self.conn is None:
            self.conn = Client(self.host, self.port, self.db, self.user, self.pw)

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]

        # Clickhouse doesn't support autoincrementing ids like Postgres, so we generate a random uuid
        return (uuid.uuid4(), time.mktime(timestamp.timetuple()), time.mktime(receipt_timestamp.timetuple()), feed, symbol, json.dumps(data))

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

        # Cross-ref data dict with user column names from custom_columns dict, inserting NULL if requested data point not present
        sequence_gen = (d[field] if d[field] else None for field in self.custom_columns.keys())
        # Iterate through the generator and surround everything except floats and NULL in single quotes
        return (uuid.uuid4(), *sequence_gen)

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
        args = [self.format(u) for u in updates]
        if self.custom_columns:
            await self.conn.execute(self.insert_statement, args)
        else:
            await self.conn.execute(f"INSERT INTO {self.table} VALUES", args)


class TradeClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRADES

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            # NULL values have to be expressed as None, not 'NULL'
            id = f"'{data['id']}'" if data['id'] else None
            otype = f"'{data['type']}'" if data['type'] else None
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, data['side'], data['amount'], data['price'], id, otype)


class FundingClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FUNDING

    def format(self, data: Tuple):
        if self.custom_columns:
            if data[4]['next_funding_time']:
                data[4]['next_funding_time'] = dt.utcfromtimestamp(data[4]['next_funding_time'])
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            ts = dt.utcfromtimestamp(data['next_funding_time']) if data['next_funding_time'] else None
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, data['mark_price'] if data['mark_price'] else None, data['rate'], ts, data['predicted_rate'])


class TickerClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TICKER

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, data['bid'], data['ask'])


class OpenInterestClickHouse(ClickHouseCallback, BackendCallback):
    default_table = OPEN_INTEREST

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, int(data['open_interest']))


class IndexClickHouse(ClickHouseCallback, BackendCallback):
    default_table = INDEX

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, data['price'])


class LiquidationsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = LIQUIDATIONS

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, data['side'], data['quantity'], data['price'], data['id'], data['status'])


class BookClickHouse(ClickHouseCallback, BackendBookCallback):
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

            return (uuid.uuid4(), timestamp, receipt_timestamp, feed, symbol, json.dumps(data))


class CandlesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = CANDLES

    def format(self, data: Tuple):
        if self.custom_columns:
            data[4]['start'] = dt.utcfromtimestamp(data[4]['start'])
            data[4]['stop'] = dt.utcfromtimestamp(data[4]['stop'])
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data = data

            open_ts = dt.utcfromtimestamp(data['start'])
            close_ts = dt.utcfromtimestamp(data['stop'])
            return (uuid.uuid4(), timestamp, receipt, exchange, symbol, open_ts, close_ts, data['interval'], data['trades'] if data['trades'] is not None else None, data['open'], data['close'], data['high'], data['low'], data['volume'], data['closed'] if data['closed'] else None)
