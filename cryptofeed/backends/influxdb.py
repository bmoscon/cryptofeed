'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import requests

from cryptofeed.defines import BID, ASK
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.exceptions import UnsupportedType
from cryptofeed.backends.backend import BackendTradeCallback, BackendBookDeltaCallback, BackendBookCallback, BackendFundingCallback, BackendTickerCallback


LOG = logging.getLogger('feedhandler')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, db: str, key=None, create_db=True, numeric_type=str, **kwargs):
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
        > select * from COINBASE-book;
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
        """
        super().__init__(addr, **kwargs)
        self.addr = f"{addr}/write?db={db}"
        self.session = None
        self.numeric_type = numeric_type
        self.key = key if key else self.default_key

        if create_db:
            r = requests.post(f'{addr}/query', data={'q': f'CREATE DATABASE {db}'})
            r.raise_for_status()

    async def write(self, feed, pair, timestamp, data):
        d = ''

        for key, value in data.items():
            if key in {'timestamp', 'feed', 'pair'}:
                continue
            if isinstance(value, str) or (self.numeric_type is str and isinstance(value, (Decimal, float))):
                d += f'{key}="{value}",'
            else:
                d += f'{key}={value},'
        d = d[:-1]

        update = f'{self.key}-{feed},pair={pair} {d},timestamp={timestamp}'
        await self.http_write('POST', update)


class TradeInflux(InfluxCallback, BackendTradeCallback):
    default_key = 'trades'

    async def write(self, feed, pair, timestamp, data):
        if data['id'] is None:
            data['id'] = 'None'
        await super().write(feed, pair, timestamp, data)


class FundingInflux(InfluxCallback, BackendFundingCallback):
    default_key = 'funding'


class InfluxBookCallback(InfluxCallback):
    default_key = 'book'

    async def _write_rows(self, start, data, timestamp):
        msg = []
        ts = int(timestamp * 1000000000)
        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        if self.numeric_type is str:
                            msg.append(f'{start} side="{side}",id="{order_id}",timestamp={timestamp},price="{price}",amount="{amount}" {ts}')
                        elif self.numeric_type is float:
                            msg.append(f'{start} side="{side}",id="{order_id}",timestamp={timestamp},price={price},amount={amount} {ts}')
                        else:
                            raise UnsupportedType(f"Type {self.numeric_type} not supported")
                        ts += 1
                else:
                    if self.numeric_type is str:
                        msg.append(f'{start} side="{side}",timestamp={timestamp},price="{price}",amount="{val}" {ts}')
                    elif self.numeric_type is float:
                        msg.append(f'{start} side="{side}",timestamp={timestamp},price={price},amount={val} {ts}')
                    else:
                        raise UnsupportedType(f"Type {self.numeric_type} not supported")
                    ts += 1
        await self.http_write('POST', '\n'.join(msg))


class BookInflux(InfluxBookCallback, BackendBookCallback):
    async def write(self, feed, pair, timestamp, data):
        start = f"{self.key}-{feed},pair={pair},delta=False"
        await self._write_rows(start, data, timestamp)


class BookDeltaInflux(InfluxBookCallback, BackendBookDeltaCallback):
    async def write(self, feed, pair, timestamp, data):
        start = f"{self.key}-{feed},pair={pair},delta=True"
        await self._write_rows(start, data, timestamp)


class TickerInflux(InfluxCallback, BackendTickerCallback):
    default_key = 'ticker'

