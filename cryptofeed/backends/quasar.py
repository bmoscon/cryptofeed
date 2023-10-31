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
        self.shard_size = shard_size
        url = f"qdb://{host}:{port}"

        pool.initialize(uri=url, user_name=username, user_private_key=private_key, cluster_public_key=public_key)

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

    async def write(self, data: dict):
        self._set_table_name(data)
        data = self.format(data)
        df = qdbpd.DataFrame(data, columns=self.columns, index=[data['timestamp']])
        # write to table, if table doesnt exist it will be created with specified shard_size value
        with pool.instance().connect() as conn:
            qdbpd.write_dataframe(df, conn, conn.table(self.table), fast=True, _async=True, create=True, shard_size=self.shard_size)


class TickerQuasar(QuasarCallback, BackendCallback):
    table_prefix = "ticker"


class TradeQuasar(QuasarCallback, BackendCallback):
    table_prefix = "trades"

    def _set_table_name(self, data: dict):
        # setting table name depending on side
        # trades/{exchange}/{symbol_1-symbol_2}/{side}
        # eg. trade/coinbase/btc-usd/buy
        super()._set_table_name(data)
        self.table = f"{self.table}/{data['side'].lower()}"


class CandlesQuasar(QuasarCallback, BackendCallback):
    table_prefix = "candles"

    def format(self, data: dict):
        data = super().format(data)
        data['start'] = datetime.utcfromtimestamp(data['start'])
        data['stop'] = datetime.utcfromtimestamp(data['stop'])
        data['closed'] = int(data['closed'])
        return data
