from datetime import datetime, timedelta
import quasardb
import quasardb.pandas as qdbpd
from cryptofeed.backends.backend import (BackendBookCallback,BackendCallback,BackendQueue)

class QuasarCallback(BackendQueue):
    def __init__(self, host="127.0.0.1", port=2836, username:str="", private_key:str="", public_key:str="", table:str=None, none_to=None):
        self.numeric_type = float
        self.table_prefix = table if table else self.default_table
        self.table = self.table_prefix
        self.running = True
        self.url = f"qdb://{host}:{port}"
        self.none_to = none_to
        self.columns=[]
        
        with quasardb.Cluster(self.url, user_name=username, user_private_key=private_key, cluster_public_key=public_key) as conn:
            self.conn = conn
    
    def format(self, data:dict):
        self.columns = list(data.keys())
        self.columns.remove('timestamp')
        data['timestamp'] = datetime.utcfromtimestamp(data['timestamp'])
        data['receipt_timestamp'] = datetime.utcfromtimestamp(data['receipt_timestamp'])
        return data

    def _set_table_name(self, data: dict):
        self.table = f"{data['exchange'].capitalize()}/{self.table_prefix}/{data['symbol']}"
                
    async def write(self, data: dict):
        self._set_table_name(data)
        data = self.format(data)
        df = qdbpd.DataFrame(data, columns=self.columns, index=[data['timestamp']])
        qdbpd.write_dataframe(df, self.conn, self.conn.table(self.table), fast=True, _async=True)

class TickerQuasar(QuasarCallback, BackendCallback):
    default_table = "Ticker"
                
class TradeQuasar(QuasarCallback, BackendCallback):
    default_table = "Trades"
        
class CandlesQuasar(QuasarCallback, BackendCallback):
    default_table = "Candles"
    
    def format(self, data: dict):
        data = super().format(data)
        data['start'] = datetime.utcfromtimestamp(data['start'])
        data['stop'] = datetime.utcfromtimestamp(data['stop'])
        return data