'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
# from influxdb import InfluxDBClient
import asyncio
from aioinflux import InfluxDBClient

import requests

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback)
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.defines import BID, ASK
from cryptofeed.exceptions import UnsupportedType
from datetime import datetime

LOG = logging.getLogger('feedhandler')


# class InfluxCallback(HTTPCallback):
#     def __init__(self, addr: str, db=None, key=None, create_db=True, numeric_type=str, org=None, bucket=None,
#                  token=None, precision='ns', username=None, password=None, **kwargs):
#         """
#         Parent class for InfluxDB callbacks
#
#         influxDB schema
#         ---------------
#         MEASUREMENT | TAGS | FIELDS
#
#         Measurement: Data Feed-Exxhange (configurable)
#         TAGS: pair
#         FIELDS: timestamp, amount, price, other funding specific fields
#
#         Example data in InfluxDB
#         ------------------------
#         > select * from "book-COINBASE";
#         name: COINBASE
#         time                amount    pair    price   side timestamp
#         ----                ------    ----    -----   ---- ---------
#         1542577584985404000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:24.963762Z
#         1542577584985404000 0.0015    BTC-USD 5542    ask  2018-11-18T21:46:24.963762Z
#         1542577585259616000 0.0018    BTC-USD 5536.17 bid  2018-11-18T21:46:25.256391Z
#
#         Parameters
#         ----------
#         addr: str
#           Address for connection. Should be in the format:
#           http(s)://<ip addr>:port
#         db: str
#           Database to write to
#         key: str
#           key to use when writing data, will be a combination of key-datatype
#         create_db: bool
#           Create database if not exists
#         numeric_type: str/float
#           Convert types before writing (amount and price)
#         org: str (For InfluxDB 2.0 compatibility)
#           Orgnaization name for authentication
#         bucket: str (For InfluxDB 2.0 compatibility)
#           Bucket name for authentication
#         token: str (For InfluxDB 2.0 compatibility)
#           Token string for authentication
#         precision: str (For InfluxDB 2.0 compatibility)
#           Precision level among (s, ms, us, ns)
#         username: str
#           Influxdb username for authentication
#         password: str
#           Influxdb password for authentication
#         """
#         super().__init__(addr, **kwargs)
#         if org and bucket and token:
#             self.addr = f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision={precision}"
#             self.headers = {"Authorization": f"Token {token}"}
#         else:
#             if create_db:
#                 r = requests.post(f'{addr}/query?u={username}&p={password}', data={'q': f'CREATE DATABASE {db}'})
#                 r.raise_for_status()
#             if username and password:
#                 self.addr = f"{addr}/write?db={db}&u={username}&p={password}"
#             else:
#                 self.addr = f"{addr}/write?db={db}"
#             self.headers = {}
#
#         self.session = None
#         self.numeric_type = numeric_type
#         self.key = key if key else self.default_key
#         # self.client = InfluxDBClient(host='localhost', port=8086, database='btc',
#         #                              username='admin', password='15348664',
#         #                              use_udp=True, udp_port=8189)
#
#
#     async def write(self, feed, pair, timestamp, receipt_timestamp, data):
#         d = ''
#
#         for key, value in data.items():
#             if key in {'timestamp', 'feed', 'pair', 'receipt_timestamp'}:
#                 continue
#             if isinstance(value, str) or (self.numeric_type is str and isinstance(value, (Decimal, float))):
#                 d += f'{key}="{value}",'
#             else:
#                 d += f'{key}={value},'
#         d = d[:-1]
#         ts = int(timestamp * 1000000000)
#
#         update = f'{self.key},feed={feed},pair={pair} {d},timestamp={timestamp},receipt_timestamp={receipt_timestamp} {ts}'
#         await self.http_write('POST', update, self.headers)

class InfluxCallback(HTTPCallback):
    def __init__(self, client_udp, key=None, **kwargs):
        """
        Parent class for InfluxDB callbacks

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Data Feed-Exxhange (configurable)
        TAGS: pair
        FIELDS: timestamp, amount, price, other funding specific fields

        Example data in InfluxDB
        ------------------------
        > select * from "book-COINBASE";
        name: COINBASE
        time                amount    pair    price   side timestamp
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
        super().__init__(client_udp, **kwargs)
        # if org and bucket and token:
        #     self.addr = f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision={precision}"
        #     self.headers = {"Authorization": f"Token {token}"}
        # else:
        #     if create_db:
        #         r = requests.post(f'{addr}/query?u={username}&p={password}', data={'q': f'CREATE DATABASE {db}'})
        #         r.raise_for_status()
        #     if username and password:
        #         self.addr = f"{addr}/write?db={db}&u={username}&p={password}"
        #     else:
        #         self.addr = f"{addr}/write?db={db}"
        #     self.headers = {}frf
        #
        # self.session = None
        self.numeric_type = float
        self.key = key if key else self.default_key
        # self.client = InfluxDBClient(host='localhost', port=8086, database='btc',
        #                              username='admin', password='15348664',
        #                              use_udp=True, udp_port=8189)
        self.client = client_udp
        self.count = 0

    async def write(self, feed, pair, timestamp, receipt_timestamp, data):
        d = ''

        for key, value in data.items():
            if key in {'timestamp', 'feed', 'pair', 'receipt_timestamp'}:
                continue
            if isinstance(value, str) or (self.numeric_type is str and isinstance(value, (Decimal, float))):
                d += f'{key}="{value}",'
            else:
                d += f'{key}={value},'
        d = d[:-1]
        ts = int(timestamp * 1000000000)

        update = f'{self.key},feed={feed},pair={pair} {d},timestamp={timestamp},receipt_timestamp={receipt_timestamp} {ts}'
        # await self.http_write('POST', update, self.headers)
        if self.count % 10000 == 0:
            logging.info([str(datetime.fromtimestamp(timestamp)), update])
        self.client.write_points([update], protocol='line')
        self.count += 1


class TradeInflux(InfluxCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingInflux(InfluxCallback, BackendFundingCallback):
    default_key = 'funding'


def book2msg(dict_book):
    N_BID = len(dict_book[BID])
    l_bid = ["bid{i}={v1},bsize{i}={v2}".format(i=N_BID - i - 1, v1=k[0], v2=k[1]) for i, k in
             enumerate(dict_book[BID].items())]
    N_ASK = len(dict_book[ASK])
    l_ask = ["ask{i}={v1},asize{i}={v2}".format(i=N_ASK - i - 1, v1=k[0], v2=k[1]) for i, k in
             enumerate(dict_book[ASK].items())]
    return ','.join(l_bid + l_ask)


class InfluxBookCallback(InfluxCallback):
    default_key = 'book'

    def _write_rows(self, start, data, timestamp, receipt_timestamp):
        # msg = []
        ts = int(timestamp * 1000000000)
        book_msg = book2msg(data)
        msg = f"""{start} {book_msg},receipt_timestamp={receipt_timestamp},timestamp={timestamp} {ts}"""
        # for side in (BID, ASK):
        #     for price, val in data[side].items():
        #         if isinstance(val, dict):
        #             for order_id, amount in val.items():
        #                 if self.numeric_type is str:
        #                     msg.append(f'{start} side="{side}",id="{order_id}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price="{price}",amount="{amount}" {ts}')
        #                 elif self.numeric_type is float:
        #                     msg.append(f'{start} side="{side}",id="{order_id}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={amount} {ts}')
        #                 else:
        #                     raise UnsupportedType(f"Type {self.numeric_type} not supported")
        #                 ts += 1
        #         else:
        #             if self.numeric_type is str:
        #                 msg.append(f'{start} side="{side}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price="{price}",amount="{val}" {ts}')
        #             elif self.numeric_type is float:
        #                 msg.append(f'{start} side="{side}",receipt_timestamp={receipt_timestamp},timestamp={timestamp},price={price},amount={val} {ts}')
        #             else:
        #                 raise UnsupportedType(f"Type {self.numeric_type} not supported")
        #             ts += 1 //this is wrong
        # logging.info(msg)
        self.client.write_points([msg], protocol='line')
        # await self.http_write('POST', msg, self.headers)


class BookInflux(InfluxBookCallback, BackendBookCallback):
    async def write(self, feed, pair, timestamp, receipt_timestamp, data):
        start = f"{self.key},feed={feed},pair={pair},delta=False"
        self._write_rows(start, data, timestamp, receipt_timestamp)


class BookDeltaInflux(InfluxBookCallback, BackendBookDeltaCallback):
    async def write(self, feed, pair, timestamp, receipt_timestamp, data):
        start = f"{self.key},feed={feed},pair={pair},delta=True"
        self._write_rows(start, data, timestamp, receipt_timestamp)


class TickerInflux(InfluxCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestInflux(InfluxCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsInflux(InfluxCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'
