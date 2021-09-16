'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.defines import BID, ASK


LOG = logging.getLogger('feedhandler')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, org: str, bucket: str, token: str, key=None, **kwargs):
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
        org: str
          Organization name for authentication
        bucket: str
          Bucket name for authentication
        token: str
          Token string for authentication
        key:
          key to use when writing data, will be a combination of key-datatype
        """
        super().__init__(addr, **kwargs)
        self.addr = f"{addr}/api/v2/write?org={org}&bucket={bucket}&precision=us"
        self.headers = {"Authorization": f"Token {token}"}

        self.session = None
        self.key = key if key else self.default_key
        self.numeric_type = float

    def format(self, data):
        ret = []
        for key, value in data.items():
            if key in {'timestamp', 'exchange', 'symbol', 'receipt_timestamp'}:
                continue
            if isinstance(value, str):
                ret.append(f'{key}="{value}"')
            else:
                ret.append(f'{key}={value}')
        return ','.join(ret)

    async def write(self, data):
        d = self.format(data)
        update = f'{self.key}-{data["exchange"]},symbol={data["symbol"]} {d},timestamp={data["timestmap"]},receipt_timestamp={data["receipt_timestamp"]} {int(data["receipt_timestamp"] * 1000000)}'
        await self.queue.put({'data': update, 'headers': self.headers})


class TradeInflux(InfluxCallback, BackendCallback):
    default_key = 'trades'

    def format(self, data):
        return f'side="{data["side"]}",price={data["price"]},amount={data["amount"]},id="{str(data["id"])}",type="{str(data["type"])}"'


class FundingInflux(InfluxCallback, BackendCallback):
    default_key = 'funding'


class BookInflux(InfluxCallback, BackendBookCallback):
    default_key = 'book'

    def format(self, data):
        delta = 'delta' in data
        book = data['book'] if not delta else data['delta']
        bids = json.dumps(book[BID])
        asks = json.dumps(book[ASK])

        return f'delta={str(delta)},{BID}="{bids}",{ASK}="{asks}"'


class TickerInflux(InfluxCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestInflux(InfluxCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsInflux(InfluxCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesInflux(InfluxCallback, BackendCallback):
    default_key = 'candles'
