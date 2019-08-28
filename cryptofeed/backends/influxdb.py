'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import requests

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.exceptions import UnsupportedType


LOG = logging.getLogger('feedhandler')


class InfluxCallback(HTTPCallback):
    def __init__(self, addr: str, db: str, create_db=True, numeric_type=str, **kwargs):
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
        numeric_type: str/float
          Convert types before writing (amount and price)
        """
        super().__init__(addr, **kwargs)
        self.addr = f"{addr}/write?db={db}"
        self.session = None
        self.numeric_type = numeric_type

        if create_db:
            r = requests.post(f'{addr}/query', data={'q': f'CREATE DATABASE {db}'})
            r.raise_for_status()

class TradeInflux(InfluxCallback):
    def __init__(self, *args, key='trades', **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        amount = str(amount)
        price = str(price)

        if order_id is None:
            order_id = 'None'
        if self.numeric_type is str:
            trade = f'{self.key}-{feed},pair={pair} side="{side}",id="{order_id}",amount="{amount}",price="{price}",timestamp={timestamp}'
        elif self.numeric_type is float:
            trade = f'{self.key}-{feed},pair={pair} side="{side}",id="{order_id}",amount={amount},price={price},timestamp={timestamp}'
        else:
            raise UnsupportedType(f"Type {self.numeric_type} not supported")

        await self.write('POST', trade)


class FundingInflux(InfluxCallback):
    def __init__(self, *args, key='funding', **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key

    async def __call__(self, *, feed, pair, **kwargs):
        data = f"{self.key}-{feed},pair={pair} "

        for key, val in kwargs.items():
            if key in {'feed', 'pair'}:
                continue
            if isinstance(val, (Decimal, float)):
                val = str(val)
                if self.numeric_type is str:
                    val = f'"{val}"'
                elif self.numeric_type is not float:
                    raise UnsupportedType(f"Type {self.numeric_type} not supported")
            elif isinstance(val, str):
                val = f'"{val}"'
            data += f"{key}={val},"

        data = data[:-1]
        await self.write('POST', data)


class InfluxBookCallback(InfluxCallback):
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
        await self.write('POST', '\n'.join(msg))


class BookInflux(InfluxBookCallback):
    def __init__(self, *args, key='book', depth=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = depth
        self.key = key
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {BID: {}, ASK: {}}
        book_convert(book, data, self.depth)

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]

        start = f"{self.key}-{feed},pair={pair},delta=False"
        await self._write_rows(start, data, timestamp)


class BookDeltaInflux(InfluxBookCallback):
    def __init__(self, *args, key='book', **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key

    async def __call__(self, *, feed, pair, delta, timestamp):
        start = f"{self.key}-{feed},pair={pair},delta=True"
        data = {BID: {}, ASK: {}}
        book_delta_convert(delta, data)
        await self._write_rows(start, data, timestamp)
