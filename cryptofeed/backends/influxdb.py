'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import aiohttp

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert


LOG = logging.getLogger('feedhandler')


class InfluxCallback:
    def __init__(self, addr: str, db: str, **kwargs):
        """
        Parent class for InfluxDB callbacks

        influxDB schema
        ---------------
        MEASUREMENT | TAGS | FIELDS

        Measurement: Exchange Name
        TAGS: trading pair, feed type (book, trades, etc), side (if applicable), order id (if applicable)
        FIELDS: timestamp, amount, price, other funding specific fields

        Example data in InfluxDB
        ------------------------
        > select * from COINBASE;
        name: COINBASE
        time                amount     feed   id       pair    price   side timestamp
        ----                ------     ----   --       ----    -----   ---- ---------
        1542577584823213000 0.00485207 trades 53989471 BTC-USD 5539    ask  2018-11-18T21:46:23.184000Z
        1542577584985404000 0.0018     book            BTC-USD 5536.17 bid  2018-11-18T21:46:24.963762Z
        1542577584985404000 0.0015     book            BTC-USD 5542    ask  2018-11-18T21:46:24.963762Z
        1542577585259616000 0.0018     book            BTC-USD 5536.17 bid  2018-11-18T21:46:25.256391Z

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

    async def write(self, data):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        async with self.session.post(self.addr, data=data) as resp:
            if resp.status != 204:
                error = await resp.text()
                LOG.error("Write to influxDB failed: %d - %s", resp.status, error)


class TradeInflux(InfluxCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        amount = float(amount)
        price = float(price)
        trade = f'{feed},pair={pair},feed=trades,side={side}'
        if order_id:
            trade += f',id={order_id}'
        trade += f' amount={amount},price={price}'

        if timestamp:
            trade += f',timestamp="{timestamp}"'

        await self.write(trade)


class FundingInflux(InfluxCallback):
    async def __call__(self, *, feed, pair, **kwargs):
        tags = ('side', 'order_id')

        data = f"{feed},pair={pair},feed=funding"
        for check in tags:
            if check in kwargs:
                data += f',{check}={kwargs[check]}'
        data += ' '

        for key, val in kwargs.items():
            if key in tags:
                continue
            if isinstance(val, Decimal):
                val = float(val)
            elif isinstance(val, str):
                val = f'"{kwargs[key]}"'
            data += f"{key}={val},"

        data = data[:-1]

        await self.write(data)


class BookInflux(InfluxCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {BID: {}, ASK: {}}
        book_convert(book, data, self.depth)

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]

        start = f"{feed},pair={pair},feed=book,"
        body = ""

        for side in (BID, ASK):
            for price, val in data[side].items():
                if isinstance(val, dict):
                    for order_id, amount in val.items():
                        body += start + f'side={side},id={order_id} timestamp="{timestamp}",price={price},amount={amount}\n'
                else:
                    body += start + f'side={side} timestamp="{timestamp}",price={price},amount={val}\n'

        await self.write(body)
