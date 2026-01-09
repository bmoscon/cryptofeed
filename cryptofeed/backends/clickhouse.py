'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from datetime import datetime as dt
import logging
from typing import Tuple

import clickhouse_connect

LOG = logging.getLogger('feedhandler')
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, INDEX, ORDER_INFO, FILLS, TRANSACTIONS, BALANCES


class ClickHouseCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', port=8123, user='default', password='', db='default', table=None, custom_columns: dict = None, none_to=None, numeric_type=float, **kwargs):
        """
        host: str
            ClickHouse server host address
        port: int
            ClickHouse HTTP port (default: 8123)
        user: str
            The name of the database user for authentication
        password: str
            Password for authentication
        db: str
            The name of the database to use
        table: str
            Table name to insert into. Defaults to default_table that should be specified in child class
        custom_columns: dict
            A dictionary which maps Cryptofeed's data type fields to ClickHouse's table column names
            Can be a subset of Cryptofeed's available fields (see the cdefs listed under each data type in types.pyx)
        """
        self.client = None
        self.table = table if table else self.default_table
        self.custom_columns = custom_columns
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.user = user
        self.db = db
        self.password = password
        self.host = host
        self.port = port
        self.running = True

    def _get_client(self):
        if self.client is None:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.db
            )
        return self.client

    def format(self, data: Tuple):
        """
        Format data tuple into a list suitable for ClickHouse batch insert
        Returns: list of values in correct order for default table schema
        """
        feed = data[0]
        symbol = data[1]
        timestamp = data[2]
        receipt_timestamp = data[3]
        data_dict = data[4]

        return [timestamp, receipt_timestamp, feed, symbol, json.dumps(data_dict)]

    def _custom_format(self, data: Tuple):
        """
        Format data using custom column mapping
        """
        d = {
            **data[4],
            **{
                'exchange': data[0],
                'symbol': data[1],
                'timestamp': data[2],
                'receipt': data[3],
            }
        }

        # Cross-ref data dict with user column names from custom_columns dict
        return [d.get(field, None) for field in self.custom_columns.keys()]

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
        client = self._get_client()
        data_rows = [self.format(u) for u in updates]

        if self.custom_columns:
            columns = list(self.custom_columns.values())
        else:
            columns = None

        try:
            # Use run_in_executor to avoid blocking the event loop when multiprocessing is disabled
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: client.insert(self.table, data_rows, column_names=columns))
        except Exception as e:
            # Log error but continue processing
            LOG.error("ClickHouse insert error: %s", e)


class TradeClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRADES

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                data_dict['side'],
                float(data_dict['amount']),
                float(data_dict['price']),
                data_dict.get('id'),
                data_dict.get('type')
            ]


class FundingClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FUNDING

    def format(self, data: Tuple):
        if self.custom_columns:
            if data[4]['next_funding_time']:
                data[4]['next_funding_time'] = dt.utcfromtimestamp(data[4]['next_funding_time'])
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            next_funding = dt.utcfromtimestamp(data_dict['next_funding_time']) if data_dict['next_funding_time'] else None
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                float(data_dict['mark_price']) if data_dict['mark_price'] else None,
                float(data_dict['rate']),
                next_funding,
                float(data_dict['predicted_rate']) if data_dict['predicted_rate'] else None
            ]


class TickerClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TICKER

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                float(data_dict['bid']),
                float(data_dict['ask'])
            ]


class OpenInterestClickHouse(ClickHouseCallback, BackendCallback):
    default_table = OPEN_INTEREST

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                float(data_dict['open_interest'])
            ]


class IndexClickHouse(ClickHouseCallback, BackendCallback):
    default_table = INDEX
    default_columns = ['timestamp', 'receipt_timestamp', 'exchange', 'symbol', 'price']
    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                float(data_dict['price'])
            ]


class LiquidationsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = LIQUIDATIONS

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                data_dict['side'],
                float(data_dict['quantity']),
                float(data_dict['price']),
                data_dict['id'],
                data_dict['status']
            ]


class CandlesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = CANDLES

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                dt.utcfromtimestamp(data_dict['start']),
                dt.utcfromtimestamp(data_dict['stop']),
                data_dict['interval'],
                float(data_dict['open']),
                float(data_dict['high']),
                float(data_dict['low']),
                float(data_dict['close']),
                float(data_dict['volume']),
                data_dict.get('closed')
            ]


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
            data_dict = data[4]

            if 'delta' in data_dict:
                book_data = json.dumps({'delta': data_dict['delta']})
            else:
                book_data = json.dumps({'snapshot': data_dict['book']})

            return [timestamp, receipt_timestamp, feed, symbol, book_data]


class OrderInfoClickHouse(ClickHouseCallback, BackendCallback):
    default_table = ORDER_INFO

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                data_dict['id'],
                data_dict.get('client_order_id'),
                data_dict['side'],
                data_dict['status'],
                data_dict['type'],
                float(data_dict['price']) if data_dict['price'] else None,
                float(data_dict['amount']),
                float(data_dict['remaining']) if data_dict['remaining'] else None,
                data_dict.get('account')
            ]


class FillsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FILLS

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                symbol,
                float(data_dict['price']),
                float(data_dict['amount']),
                data_dict['side'],
                data_dict.get('fee'),
                data_dict['id'],
                data_dict['order_id'],
                data_dict.get('liquidity'),
                data_dict['type'],
                data_dict.get('account')
            ]


class TransactionsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRANSACTIONS

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                data_dict['currency'],
                data_dict['type'],
                data_dict['status'],
                float(data_dict['amount'])
            ]


class BalancesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = BALANCES

    def format(self, data: Tuple):
        if self.custom_columns:
            return self._custom_format(data)
        else:
            exchange, symbol, timestamp, receipt, data_dict = data
            return [
                timestamp,
                receipt,
                exchange,
                data_dict['currency'],
                float(data_dict['balance']),
                float(data_dict.get('reserved', 0))
            ]
