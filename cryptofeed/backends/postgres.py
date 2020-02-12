'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
from decimal import Decimal
import json

import asyncpg

from cryptofeed.defines import TRADES, FUNDING, TICKER, OPEN_INTEREST
from cryptofeed.backends.backend import BackendTradeCallback, BackendTickerCallback, BackendFundingCallback, BackendOpenInterestCallback, BackendBookCallback, BackendBookDeltaCallback


class PostgresCallback:
    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, table=None, numeric_type=float, **kwargs):
        """
        library: str
            Postgres library. Will be created if does not exist.
        key: str
            setting key lets you override the symbol name.
            The defaults are related to the data
            being stored, i.e. trade, funding, etc
        kwargs:
            if library needs to be created you can specify the
            lib_type in the kwargs. Default is VersionStore, but you can
            set to chunkstore with lib_type=Postgres.CHUNK_STORE
        """
        self.conn = None
        self.table = table if table else self.default_table
        self.numeric_type = numeric_type
        self.user = user
        self.db = db
        self.pw = pw
        self.host = host

    async def _connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(user=self.user, password=self.pw, database=self.db, host=self.host)

    async def write(self, feed, pair, timestamp, data):
        await self._connect()
        async with self.conn.transaction():
            time = dt.utcfromtimestamp(timestamp)
            await self.conn.execute(f"INSERT INTO {self.table} VALUES('{feed}','{pair}','{time}',{data})")


class TradePostgres(PostgresCallback, BackendTradeCallback):
    default_table = TRADES

    async def write(self, feed, pair, timestamp, data):
        if 'id' in data:
            d = f"'{data['side']}',{data['amount']},{data['price']},'{data['id']}'"
        else:
            d = f"'{data['side']}',{data['amount']},{data['price']},NULL"
        await super().write(feed, pair, timestamp, d)


class FundingPostgres(PostgresCallback, BackendFundingCallback):
    default_table = FUNDING

    async def write(self, feed, pair, timestamp, data):
        await super().write(feed, pair, timestamp, f"'{json.dumps(data)}'")


class TickerPostgres(PostgresCallback, BackendTickerCallback):
    default_table = TICKER

    async def write(self, feed, pair, timestamp, data):
        d = f"{data['bid']},{data['ask']}"
        await super().write(feed, pair, timestamp, d)


class OpenInterestPostgres(PostgresCallback, BackendOpenInterestCallback):
    default_table = OPEN_INTEREST


class BookPostgres(PostgresCallback, BackendBookCallback):
    default_table = 'book'

    async def write(self, feed, pair, timestamp, data):
        await super().write(feed, pair, timestamp, f"'{json.dumps(data)}'")


class BookDeltaPostgres(PostgresCallback, BackendBookDeltaCallback):
    default_table = 'book'

    async def write(self, feed, pair, timestamp, data):
        await super().write(feed, pair, timestamp, f"'{json.dumps(data)}'")
