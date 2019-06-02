'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import aiohttp
import requests

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


LOG = logging.getLogger('feedhandler')


class InfluxCallback:
    def __init__(self, addr: str, db: str, create_db=True, **kwargs):
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
        """
        self.addr = f"{addr}/write?db={db}"
        self.session = None

        if create_db:
            r = requests.post(f'{addr}/query', data={'q': f'CREATE DATABASE {db}'})
            if r.status_code != 200:
                r.raise_for_status()

    async def write(self, data):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        async with self.session.post(self.addr, data=data) as resp:
            if resp.status != 204:
                error = await resp.text()
                LOG.error("Write to influxDB failed: %d - %s", resp.status, error)


class TradeInflux(InfluxCallback):
    def __init__(self, *args, key='trades', **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        amount = str(amount)
        price = str(price)

        if order_id is None:
            order_id = 'None'
        trade = f'{self.key}-{feed},pair={pair} side="{side}",id="{order_id}",amount="{amount}",price="{price}",timestamp={timestamp}'

        await self.write(trade)


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
            elif isinstance(val, str):
                val = f'"{kwargs[key]}"'
            data += f"{key}={val},"

        data = data[:-1]
        await self.write(data)


class BookInflux(InfluxCallback):
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
        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        await self.write(f'{start} side="{side}",id="{order_id}",timestamp={timestamp},price="{price}",amount="{amount}"')
                else:
                    await self.write(f'{start} side="{side}",price="{price}",timestamp={timestamp},amount="{val}"')


class BookDeltaInflux(InfluxCallback):
    def __init__(self, *args, key='book', **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key

    async def __call__(self, *, feed, pair, delta, timestamp):
        start = f"{self.key}-{feed},pair={pair},delta=True"
        data = {BID: {}, ASK: {}}
        book_delta_convert(delta, data)
        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        await self.write(f'{start} side="{side}",id="{order_id}",timestamp={timestamp},price="{price}",amount="{amount}"')
                else:
                    await self.write(f'{start} side="{side}",price="{price}",timestamp={timestamp},amount="{val}"')
