'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime as dt
from typing import Tuple

import asyncpg
from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendQueue, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendFuturesIndexCallback, BackendMarketInfoCallback,
                                         BackendTransactionsCallback)
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, FUTURES_INDEX, MARKET_INFO, TRANSACTIONS


class PostgresCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', user=None, pw=None, db=None, table=None, numeric_type=float, cache_size=0, **kwargs):
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

    async def _connect(self):
        if self.conn is None:
            self.conn = await asyncpg.connect(user=self.user, password=self.pw, database=self.db, host=self.host)

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]

        return f"(DEFAULT,'{timestamp}','{receipt_timestamp}','{feed}','{symbol}','{json.dumps(data)}')"

    async def writer(self):
        while True:
            if self._cache_size:
                async with self.read_many_queue(self._cache_size) as updates:
                    await self.write_cache(updates)
            else:
                async with self.read_queue() as update:
                    await self.write_cache([update])

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        ts = dt.utcfromtimestamp(timestamp)
        rts = dt.utcfromtimestamp(receipt_timestamp)
        await self.queue.put((feed, symbol, ts, rts, data))

    async def write_cache(self, updates: list):
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
                await self.write_cache(updates)


class TradePostgres(PostgresCallback, BackendTradeCallback):
    default_table = TRADES

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]
        if 'id' not in data:
            data['id'] = 'NULL'
        else:
            data['id'] = f"'{data['id']}'"

        if 'order_type' not in data:
            data['order_type'] = 'NULL'
        else:
            data['order_type'] = f"'{data['order_type']}'"

        return f"(DEFAULT,'{timestamp}','{receipt_timestamp}','{feed}','{symbol}','{data['side']}',{data['amount']},{data['price']},{data['id']},{data['order_type']})"


class FundingPostgres(PostgresCallback, BackendFundingCallback):
    default_table = FUNDING


class TickerPostgres(PostgresCallback, BackendTickerCallback):
    default_table = TICKER

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]

        return f"(DEFAULT,'{timestamp}','{receipt_timestamp}','{feed}','{symbol}',{data['bid']},{data['ask']})"


class OpenInterestPostgres(PostgresCallback, BackendOpenInterestCallback):
    default_table = OPEN_INTEREST


class FuturesIndexPostgres(PostgresCallback, BackendFuturesIndexCallback):
    default_table = FUTURES_INDEX


class LiquidationsPostgres(PostgresCallback, BackendLiquidationsCallback):
    default_table = LIQUIDATIONS


class BookPostgres(PostgresCallback, BackendBookCallback):
    default_table = 'book'


class BookDeltaPostgres(PostgresCallback, BackendBookDeltaCallback):
    default_table = 'book'


class MarketInfoPostgres(PostgresCallback, BackendMarketInfoCallback):
    default_table = MARKET_INFO


class TransactionsPostgres(PostgresCallback, BackendTransactionsCallback):
    default_table = TRANSACTIONS


class CandlesPostgres(PostgresCallback, BackendCandlesCallback):
    default_table = CANDLES

    def format(self, data: Tuple):
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data = data[4]

        open_ts = dt.utcfromtimestamp(data['start'])
        close_ts = dt.utcfromtimestamp(data['stop'])
        return f"(DEFAULT,'{timestamp}','{receipt_timestamp}','{feed}','{symbol}','{open_ts}','{close_ts}','{data['interval']}',{data['trades']},{data['open_price']},{data['close_price']},{data['high_price']},{data['low_price']},{data['volume']},{data['closed']})"
