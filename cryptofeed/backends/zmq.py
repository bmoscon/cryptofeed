'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import zmq
import zmq.asyncio

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert


class ZMQCallback:
    def __init__(self, host='127.0.0.1', port=5555, zmq_type=zmq.PUSH, **kwargs):
        url = "tcp://{}:{}".format(host, port)
        ctx = zmq.asyncio.Context.instance()
        self.con = ctx.socket(zmq_type)
        self.con.bind(url)


class TradeZMQ(ZMQCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp, 'side': side, 'amount': float(amount), 'price': float(price)}
        data = {'type': 'trade', 'data': trade}
        await self.con.send_json(data)


class FundingZMQ(ZMQCallback):
    async def __call__(self, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        data = {'type': 'funding', 'data': kwargs}
        await self.con.send_json(data)


class BookZMQ(ZMQCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data, self.depth)
        upd = {'type': 'book', 'feed': feed, 'pair': pair, 'data': data}

        if self.depth:
            if upd['data'][BID] == self.previous[BID] and upd['data'][ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = upd['data'][ASK]
            self.previous[BID] = upd['data'][BID]

        await self.con.send_json(upd)
