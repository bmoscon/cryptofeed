'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal

import requests

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.defines import BID, ASK
from cryptofeed.exceptions import UnsupportedType


LOG = logging.getLogger('feedhandler')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, db=None, key=None, create_db=False, numeric_type=str, org=None, bucket=None, token=None, precision='ns', username=None, password=None, **kwargs):
        """
        Parent class for InfluxDB callbacks

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exchange (configurable)
        TAGS: symbol
        FIELDS: timestamp, amount, price, other funding specific fields

        Example data in InfluxDB
        ------------------------
        > select * from "book-COINBASE";
        name: COINBASE
        time                amount    symbol    price   side timestamp
        ----                ------    ----    -----   ---- ---------
        1542577584985404000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:24.963762Z
        1542577584985404000 0.0015    BTC-USD 5542    ask  2018-11-18T21:46:24.963762Z
        1542577585259616000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:25.256391Z

        Parameters
        ----------
        addr: str
          Address for connection. Should be in the format:
          http(s)://<ip addr>:port
        db: str
          Database to write to
        key: str
          key to use when writing data, will be a combination of key-datatype
        create_db: bool
          Create database if not exists
        numeric_type: str/float
          Convert types before writing (amount and price)
        org: str (For InfluxDB 2.0 compatibility)
          Orgnaization name for authentication
        bucket: str (For InfluxDB 2.0 compatibility)
          Bucket name for authentication
        token: str (For InfluxDB 2.0 compatibility)
          Token string for authentication
        precision: str (For InfluxDB 2.0 compatibility)
          Precision level among (s, ms, us, ns)
        username: str
          Influxdb username for authentication
        password: str
          Influxdb password for authentication
        """
        super().__init__(addr, **kwargs)
        if org and bucket and token:
            self.addr = f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision={precision}"
            self.headers = {"Authorization": f"Token {token}"}
        else:
            if create_db:
                r = requests.post(f'{addr}/query?u={username}&p={password}', data={'q': f'CREATE DATABASE {db}'})
                r.raise_for_status()
            if username and password:
                self.addr = f"{addr}/write?db={db}&u={username}&p={password}"
            else:
                self.addr = f"{addr}/write?db={db}"
            self.headers = {}

        self.session = None
        self.numeric_type = numeric_type
        self.key = key if key else self.default_key

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        d = ''

        for key, value in data.items():
            if key in {'timestamp', 'feed', 'symbol', 'receipt_timestamp'}:
                continue
            if isinstance(value, str) or (self.numeric_type is str and isinstance(value, (Decimal, float))):
                d += f'{key}="{value}",'
            else:
                d += f'{key}={value},'
        d = d[:-1]

        update = f'{self.key}-{feed},symbol={symbol} {d},timestamp={timestamp},receipt_timestamp={receipt_timestamp}'
        await self.queue.put({'data': update, 'headers': self.headers})


class TradeInflux(InfluxCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingInflux(InfluxCallback, BackendFundingCallback):
    default_key = 'funding'


class InfluxBookCallback(InfluxCallback):
    default_key = 'book'

    async def _write_rows(self, start, data, timestamp, receipt_timestamp):
        msg = []
        ts = int(timestamp * 1000000000)
        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        if self.numeric_type is str:
                            msg.append(f'{start} side="{side}",id="{order_id}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price="{price}",amount="{amount}" {ts}')
                        elif self.numeric_type is float:
                            msg.append(f'{start} side="{side}",id="{order_id}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={amount} {ts}')
                        else:
                            raise UnsupportedType(f"Type {self.numeric_type} not supported")
                        ts += 1
                else:
                    if self.numeric_type is str:
                        msg.append(f'{start} side="{side}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price="{price}",amount="{val}" {ts}')
                    elif self.numeric_type is float:
                        msg.append(f'{start} side="{side}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={val} {ts}')
                    else:
                        raise UnsupportedType(f"Type {self.numeric_type} not supported")
                    ts += 1
        await self.queue.put({'data': '\n'.join(msg), 'headers': self.headers})


class BookInflux(InfluxBookCallback, BackendBookCallback):
    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        start = f"{self.key}-{feed},symbol={symbol},delta=False"
        await self._write_rows(start, data, timestamp, receipt_timestamp)


class BookDeltaInflux(InfluxBookCallback, BackendBookDeltaCallback):
    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        start = f"{self.key}-{feed},symbol={symbol},delta=True"
        await self._write_rows(start, data, timestamp, receipt_timestamp)


class TickerInflux(InfluxCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestInflux(InfluxCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsInflux(InfluxCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoInflux(InfluxCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsInflux(InfluxCallback, BackendTransactionsCallback):
    default_key = 'transactions'


class CandlesInflux(InfluxCallback, BackendCandlesCallback):
    default_key = 'candles'
