from datetime import datetime, timedelta
import quasardb.pool as pool
import quasardb.pandas as qdbpd
from cryptofeed.backends.backend import (BackendCallback, BackendQueue)


class QuasarCallback(BackendQueue):
    def __init__(self, host="127.0.0.1", port=2836, username: str = "", private_key: str = "", public_key: str = "", none_to=None, shard_size: timedelta = timedelta(minutes=15)):
        self.numeric_type = float
        self.table = ""
        self.running = True
        self.none_to = none_to
        self.columns = []
        self.shard_size = self._get_str_timedelta(shard_size)
        url = f"qdb://{host}:{port}"

        pool.initialize(uri=url, user_name=username, user_private_key=private_key, cluster_public_key=public_key)

    def _get_str_timedelta(self, delta: timedelta):
        # calculate the number of hours, minutes, and remaining seconds from timedelta, return it in correct format for query
        hours, remainder = divmod(delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}hour {int(minutes)}min {int(seconds)}s"

    def format(self, data: dict):
        self.columns = list(data.keys())
        self.columns.remove('timestamp')
        data['timestamp'] = datetime.utcfromtimestamp(data['timestamp'])
        data['receipt_timestamp'] = datetime.utcfromtimestamp(data['receipt_timestamp'])
        return data

    def _set_table_name(self, data: dict):
        # setting table name
        # {channel}/{exchange}/{symbol_1-symbol_2}
        # eg. ticker/coinbase/btc-usd
        self.table = f"{self.table_prefix.lower()}/{data['exchange'].lower()}/{data['symbol'].lower()}"

    def _create_table(self, conn):
        if not conn.table(self.table).exists():
            conn.query(self.query)

    async def write(self, data: dict):
        self._set_table_name(data)
        self._create_query()
        data = self.format(data)
        df = qdbpd.DataFrame(data, columns=self.columns, index=[data['timestamp']])
        # write to table, if table doesnt exist it will be created with specified shard_size value
        with pool.instance().connect() as conn:
            self._create_table(conn)
            qdbpd.write_dataframe(df, conn, conn.table(self.table), fast=True, _async=True)


class TickerQuasar(QuasarCallback, BackendCallback):
    table_prefix = "ticker"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), bid DOUBLE, ask DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class TradeQuasar(QuasarCallback, BackendCallback):
    table_prefix = "trades"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), side SYMBOL(side), amount DOUBLE, price DOUBLE, id STRING, type STRING, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class CandlesQuasar(QuasarCallback, BackendCallback):
    table_prefix = "candles"

    def format(self, data: dict):
        data = super().format(data)
        data['start'] = datetime.utcfromtimestamp(data['start'])
        data['stop'] = datetime.utcfromtimestamp(data['stop'])
        data['closed'] = int(data['closed'])
        return data

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), start TIMESTAMP, stop TIMESTAMP, interval STRING, trades STRING, open DOUBLE, close DOUBLE, high DOUBLE, low DOUBLE, volume DOUBLE, closed INT64, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class FundingQuasar(QuasarCallback, BackendCallback):
    table_prefix = "funding"

    def format(self, data: dict):
        data = super().format(data)
        data['next_funding_time'] = datetime.utcfromtimestamp(data['next_funding_time'])
        return data

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), mark_price DOUBLE, rate DOUBLE, next_funding_time TIMESTAMP, predicted_rate DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class BookQuasar(QuasarCallback, BackendCallback):
    table_prefix = "book"

    def format(self, data: dict):
        data = super().format(data)
        if not data['book']:
            best_bid = max(data["delta"]["bid"], key=lambda x: x[0])
            best_ask = min(data["delta"]["ask"], key=lambda x: x[0])

            data['best_bid_price'] = best_bid[0]
            data['best_bid_amount'] = best_bid[1]
            data['best_ask_price'] = best_ask[0]
            data['best_ask_amount'] = best_ask[1]
        else:
            best_bid = max(data["book"]["bid"].keys())
            best_ask = min(data["book"]["ask"].keys())

            data['best_bid_price'] = best_bid
            data['best_bid_amount'] = data["book"]["bid"][best_bid]
            data['best_ask_price'] = best_ask
            data['best_ask_amount'] = data["book"]["ask"][best_ask]
        self.columns = list(data.keys())
        self.columns.remove('book')
        self.columns.remove('delta')
        return data

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), best_bid_price DOUBLE, best_bid_amount DOUBLE, best_ask_price DOUBLE, best_ask_amount DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class LiquidationsQuasar(QuasarCallback, BackendCallback):
    table_prefix = "liquidations"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), side SYMBOL(side), quantity DOUBLE, price DOUBLE, id STRING, status STRING, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class OpenInterestQuasar(QuasarCallback, BackendCallback):
    table_prefix = "open_intrerest"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), open_interest INT64, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class OrderInfoQuasar(QuasarCallback, BackendCallback):
    table_prefix = "order_info"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), id STRING, client_order_id STRING, side SYMBOL(side), status STRING, type STRING, price DOUBLE, amount DOUBLE, remaining DOUBLE, account STRING, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class TransactionsQuasar(QuasarCallback, BackendCallback):
    table_prefix = "transactions"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), currency SYMBOL(currency), type STRING, status STRING, amount DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class BalancesQuasar(QuasarCallback, BackendCallback):
    table_prefix = "balances"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), currency SYMBOL(currency), balance DOUBLE, reserved DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class FillsQuasar(QuasarCallback, BackendCallback):
    table_prefix = "fills"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), price DOUBLE, amount DOUBLE, side SYMBOL(side), fee DOUBLE, id STRING, order_id STRING, liquidity DOUBLE, type STRING, account STRING, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'


class IndexQuasar(QuasarCallback, BackendCallback):
    table_prefix = "index"

    def _create_query(self):
        self.query = f'CREATE TABLE "{self.table}" (exchange SYMBOL(exchange), symbol SYMBOL(symbol), price DOUBLE, receipt_timestamp TIMESTAMP) SHARD_SIZE = {self.shard_size}'
