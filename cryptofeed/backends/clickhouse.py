'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from clickhouse_connect import Client
from cryptofeed.backends.backend import BackendCallback, BackendQueue
from cryptofeed.defines import TRADES, FUNDING, TICKER, OPEN_INTEREST, LIQUIDATIONS, CANDLES, ORDER_INFO, TRANSACTIONS, BALANCES, FILLS


class ClickHouseCallback(BackendQueue):
    def __init__(self, database, host='localhost', port=9000, user='default', password='', table=None, **kwargs):
        self.client = Client(host=host, port=port, user=user, password=password, database=database)
        self.table = table if table else self.default_table
        self.running = True

    async def writer(self):
        while self.running:
            async with self.read_queue() as updates:
                for update in updates:
                    self.client.insert(self.table, [update])


class TradeClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRADES


class FundingClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FUNDING


class TickerClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TICKER


class OpenInterestClickHouse(ClickHouseCallback, BackendCallback):
    default_table = OPEN_INTEREST


class LiquidationsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = LIQUIDATIONS


class CandlesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = CANDLES


class OrderInfoClickHouse(ClickHouseCallback, BackendCallback):
    default_table = ORDER_INFO


class TransactionsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = TRANSACTIONS


class BalancesClickHouse(ClickHouseCallback, BackendCallback):
    default_table = BALANCES


class FillsClickHouse(ClickHouseCallback, BackendCallback):
    default_table = FILLS
