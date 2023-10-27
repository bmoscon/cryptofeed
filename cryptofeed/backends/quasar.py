from datetime import datetime, timedelta
import quasardb
import quasardb.pandas as qdbpd
from cryptofeed.backends.backend import (BackendBookCallback,BackendCallback,BackendQueue)

class QuasarCallback(BackendQueue):
    def __init__(self, host="127.0.0.1", port=2836, username:str="", private_key:str="", public_key:str="", table:str=None, none_to=None):
        self.numeric_type = float
        self.table = table if table else self.default_table
        self.running = True
        self.url = f"qdb://{host}:{port}"
        self.none_to = none_to
        
        with quasardb.Cluster(self.url, user_name=username, user_private_key=private_key, cluster_public_key=public_key) as conn:
            self.conn = conn
            
    def format(self, data:dict):
        data['timestamp'] = datetime.utcfromtimestamp(data['timestamp'])
        data['receipt_timestamp'] = datetime.utcfromtimestamp(data['receipt_timestamp'])
        return data
                
    async def write(self, data: dict):
        data = self.format(data)
        df = qdbpd.DataFrame(data, columns=data.keys(), index=[data['timestamp']])
        qdbpd.write_dataframe(df, self.conn, self.conn.table(self.table), fast=True, _async=True)

class CandlesQuasar(QuasarCallback, BackendCallback):
    default_table = "Candles"
    
    def format(self, data: dict):
        data = super().format(data)
        data['start'] = datetime.utcfromtimestamp(data['start'])
        data['stop'] = datetime.utcfromtimestamp(data['stop'])
        return data

class FundingQuasar(QuasarCallback, BackendCallback):
    default_table = "Funding"
    
    def format(self, data: dict):
        data = super().format(data)
        data['next_funding_time'] = datetime.utcfromtimestamp(data['next_funding_time'])
        return data
    
class OpenInterestQuasar(QuasarCallback, BackendBookCallback):
    # TODO
    default_table = "OpenInterest"   
     
    def __init__(self, *args, snapshots_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.snapshots_only = snapshots_only

    
class TickerQuasar(QuasarCallback, BackendCallback):
    default_table = "Ticker"

class TradeQuasar(QuasarCallback, BackendCallback):
    default_table = "Trades"
                            
class LiquidationsQuasar(QuasarCallback, BackendCallback):
    default_table = "Liquidations"
    
class IndexQuasar(QuasarCallback, BackendCallback):
    default_table = "Index"

class OrderQuasar(QuasarCallback, BackendCallback):
    # no chanel found to use this class with
    default_table = "Orders"
    
    def __init__(self, host="127.0.0.1", port=2836, username: str = "", private_key: str = "", public_key: str = "", table: str = None, none_to=None):
        super().__init__(host, port, username, private_key, public_key, table, none_to)
        self._create_table()
         
    def _create_table(self):
        # creating separate tables for buy and sell for quasardb orderbook() function
        tables = [self.conn.table(self.table+"/sell"), self.conn.table(self.table+"/buy")]
        for t in tables:
            if t.exists() is False:
                # $timestamp, $table, type, reason, order_id, sequence, price, size, funds - tables required for orderbook to work
                cols = [
                    # tables required for orderbook to work
                    quasardb.ColumnInfo(quasardb.ColumnType.String, "type"),    # symbol
                    quasardb.ColumnInfo(quasardb.ColumnType.String, "order_id"),
                    quasardb.ColumnInfo(quasardb.ColumnType.Int64, "sequence"), # id
                    quasardb.ColumnInfo(quasardb.ColumnType.String, "reason"),
                    quasardb.ColumnInfo(quasardb.ColumnType.Double, "size"),    # amount
                    quasardb.ColumnInfo(quasardb.ColumnType.Double, "price"),   # price
                    quasardb.ColumnInfo(quasardb.ColumnType.Double, "funds"),
                    # additional tables
                    quasardb.ColumnInfo(quasardb.ColumnType.String, "exchange"),
                    quasardb.ColumnInfo(quasardb.ColumnType.Timestamp, "receipt_timestamp")
                ]
                t.create(cols, timedelta(minutes=15))
                
    def format(self, data:dict):
        data['timestamp'] = datetime.utcfromtimestamp(data['timestamp'])
        data['receipt_timestamp'] = datetime.utcfromtimestamp(data['receipt_timestamp'])
        data['type'] = data.pop('symbol')
        data['sequence'] = data.pop('id')
        data['size'] = data.pop('amount')
        return data
        
    
    async def write(self, data: dict):
        data=self.format(data)
        df = qdbpd.DataFrame(data, columns=data.keys(), index=[data['timestamp']])
        # write to diffrent tables
        if data["side"] == 'buy':
            qdbpd.write_dataframe(df, self.conn, self.conn.table(self.table+"/buy"), fast=True, _async=True)
        if data["side"] == 'sell':
            qdbpd.write_dataframe(df, self.conn, self.conn.table(self.table+"/sell"), fast=True, _async=True)    
