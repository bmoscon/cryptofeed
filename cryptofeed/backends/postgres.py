'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from datetime import datetime as dt
from typing import Tuple

import asyncpg
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, INDEX


class PostgresCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, port=None, table=None, numeric_type=float, max_batch=100, **kwargs):
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
        max_batch: int
            maximum batch size to use when writing rows to postgres
        """
        self.conn = None
        self.table = table if table else self.default_table
        self.numeric_type = numeric_type
        self.user = user
        self.db = db
        self.pw = pw
        self.host = host
        self.port = port
        self.max_batch = max_batch

    async def _connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(user=self.user, password=self.pw, database=self.db, host=self.host, port=self.port)

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]

        return f"(DEFAULT,'{timestamp}','{receipt_timestamp}','{feed}','{symbol}','{json.dumps(data)}')"

    async def writer(self):
        while True:
            size = max(self.queue.qsize(), 1)
            size = min(self.max_batch, size)
            async with self.read_many_queue(size) as updates:
                await self.write_batch(updates)

    async def write(self, data: dict):
        ts = dt.utcfromtimestamp(data['timestamp']) if data['timestamp'] else None
        rts = dt.utcfromtimestamp(data['receipt_timestamp'])
        await self.queue.put((data['exchange'], data['symbol'], ts, rts, data))

    async def write_batch(self, updates: list):
        await self._connect()

        args_str = ','.join([self.format(u) for u in updates])

        async with self.conn.transaction():
            try:
                await self.conn.execute(f"INSERT INTO {self.table} VALUES {args_str}")
            except asyncpg.UniqueViolationError:
                # when restarting a subscription, some exchanges will re-publish a few messages
                pass

    async def stop(self):
        if self.queue.qsize() > 0:
            async with self.read_many_queue(self.queue.qsize()) as updates:
                await self.write_batch(updates)


class TradePostgres(PostgresCallback, BackendCallback):
    default_table = TRADES

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        id = f"'{data['id']}'" if data['id'] else 'NULL'
        otype = f"'{data['type']}'" if data['type'] else 'NULL'
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}','{data['side']}',{data['amount']},{data['price']},{id},{otype})"


class FundingPostgres(PostgresCallback, BackendCallback):
    default_table = FUNDING

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        ts = dt.utcfromtimestamp(data['next_funding_time']) if data['next_funding_time'] else 'NULL'
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}',{data['mark_price'] if data['mark_price'] else 'NULL'},{data['rate']},'{ts}',{data['predicted_rate']})"


class TickerPostgres(PostgresCallback, BackendCallback):
    default_table = TICKER

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}',{data['bid']},{data['ask']})"


class OpenInterestPostgres(PostgresCallback, BackendCallback):
    default_table = OPEN_INTEREST

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}',{data['open_interest']})"


class IndexPostgres(PostgresCallback, BackendCallback):
    default_table = INDEX

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}',{data['price']})"


class LiquidationsPostgres(PostgresCallback, BackendCallback):
    default_table = LIQUIDATIONS

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}',{data['price']},'{data['side']}',{data['quantity']},{data['price']},'{data['id']}','{data['status']}')"


class BookPostgres(PostgresCallback, BackendBookCallback):
    default_table = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class CandlesPostgres(PostgresCallback, BackendCallback):
    default_table = CANDLES

    def format(self, data: Tuple):
        exchange, symbol, timestamp, receipt, data = data

        open_ts = dt.utcfromtimestamp(data['start'])
        close_ts = dt.utcfromtimestamp(data['stop'])
        return f"(DEFAULT,'{timestamp}','{receipt}','{exchange}','{symbol}','{open_ts}','{close_ts}','{data['interval']}',{data['trades'] if data['trades'] is not None else 'NULL'},{data['open']},{data['close']},{data['high']},{data['low']},{data['volume']},{data['closed'] if data['closed'] else 'NULL'})"
