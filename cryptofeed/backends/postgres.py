'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
from decimal import Decimal

import asyncpg
from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendFuturesIndexCallback, BackendMarketInfoCallback,
                                         BackendTransactionsCallback, DeribitBackendTickerCallback, DeribitBackendTradeCallback,
                                         DeribitBackendBookCallback)
from cryptofeed.defines import FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, FUTURES_INDEX, MARKET_INFO, TRANSACTIONS


class PostgresCallback:
    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, table=None, numeric_type=Decimal, cache_size=0, **kwargs):
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
        cache_size: int
            Number of lines to cache before writing the whole as a batch. Defaults to 0, meaning no caching.
        """
        self.conn = None
        self.table = table if table else self.default_table
        self.numeric_type = numeric_type
        self.user = user
        self.db = db
        self.pw = pw
        self.host = host

        self._cache_size = cache_size
        self._cache = []
        self._cache_counter = 0

    async def _connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(user=self.user, password=self.pw, database=self.db, host=self.host)

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        time = dt.utcfromtimestamp(timestamp)
        rtime = dt.utcfromtimestamp(receipt_timestamp)

        self._cache.append(f"('{symbol}','{time}',{data})")
        self._cache_counter += 1

        if self._cache_counter > self._cache_size:
            await self.write_cache()

    async def write_cache(self):
        await self._connect()

        async with self.conn.transaction():
            args_str = ','.join(line for line in self._cache)

            self._cache_counter = 0
            self._cache.clear()

            try:
                await self.conn.execute(f"INSERT INTO {self.table} VALUES {args_str}")
            except asyncpg.UniqueViolationError:
                # when restarting a subscription, some exchanges will re-publish a few messages
                pass

    async def stop(self):
        if self._cache_counter > 0:
            await self.write_cache()


class TradePostgres(PostgresCallback, BackendTradeCallback):
    default_table = TRADES

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        if 'id' in data:
            d = f"'{data['side']}',{data['amount']},{data['price']},'{data['id']}'"
        else:
            d = f"'{data['side']}',{data['amount']},{data['price']},NULL"
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class DeribitTradePostgres(PostgresCallback, DeribitBackendTradeCallback):
    default_table = TRADES

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = ','.join('NULL' if val is None else str(val) if type(val) == self.numeric_type else f'\'{val}\'' for val in data.values())
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class FundingPostgres(PostgresCallback, BackendFundingCallback):
    default_table = FUNDING

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await super().write(feed, symbol, timestamp, receipt_timestamp, f"'{json.dumps(data)}'")


class TickerPostgres(PostgresCallback, BackendTickerCallback):
    default_table = TICKER

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = f"{data['bid']},{data['ask']}"
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class DeribitTickerPostgres(PostgresCallback, DeribitBackendTickerCallback):
    default_table = 'tickers'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = ','.join('NULL' if val is None else str(val) if type(val) == self.numeric_type else f'\'{val}\'' for val in data.values())
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class OpenInterestPostgres(PostgresCallback, BackendOpenInterestCallback):
    default_table = OPEN_INTEREST

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = f"{data['open_interest']}"
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class FuturesIndexPostgres(PostgresCallback, BackendFuturesIndexCallback):
    default_table = FUTURES_INDEX

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = f"{data['futures_index']}"
        await super().write(feed, symbol, timestamp, receipt_timestamp, d)


class LiquidationsPostgres(PostgresCallback, BackendLiquidationsCallback):
    default_table = LIQUIDATIONS


class BookPostgres(PostgresCallback, BackendBookCallback):
    default_table = 'book'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await super().write(feed, symbol, timestamp, receipt_timestamp, f"'{json.dumps(data)}'")


class DeribitBookPostgres(PostgresCallback, DeribitBackendBookCallback):
    default_table = 'books'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await super().write(feed, symbol, timestamp, receipt_timestamp, f"'{json.dumps(data)}'")


class BookDeltaPostgres(PostgresCallback, BackendBookDeltaCallback):
    default_table = 'book'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await super().write(feed, symbol, timestamp, receipt_timestamp, f"'{json.dumps(data)}'")


class MarquetInfoPostgres(PostgresCallback, BackendMarketInfoCallback):
    default_table = MARKET_INFO


class TransactionsPostgres(PostgresCallback, BackendTransactionsCallback):
    default_table = TRANSACTIONS
