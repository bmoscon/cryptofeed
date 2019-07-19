'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import json

import zmq
import zmq.asyncio

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class ZMQCallback:
    def __init__(self, host='127.0.0.1', port=5555, **kwargs):
        url = "tcp://{}:{}".format(host, port)
        ctx = zmq.asyncio.Context.instance()
        self.con = ctx.socket(zmq.PUB)
        self.con.connect(url)


class TradeZMQ(ZMQCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp, 'side': side, 'amount': float(amount), 'price': float(price)}
        await self.con.send_string(f'trades {json.dumps(trade)}')

class FundingZMQ(ZMQCallback):
    async def __call__(self, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        await self.con.send_string(f'funding {json.dumps(kwargs)}')


class BookZMQ(ZMQCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data, self.depth)
        upd = {'feed': feed, 'pair': pair, 'delta': False, 'data': data}

        if self.depth:
            if upd['data'][BID] == self.previous[BID] and upd['data'][ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = upd['data'][ASK]
            self.previous[BID] = upd['data'][BID]

        await self.con.send_string(f'book {json.dumps(upd)}')


class BookDeltaZMQ(ZMQCallback):
    async def __call__(self, *, feed, pair, delta, timestamp):
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_delta_convert(delta, data)
        upd = {'feed': feed, 'pair': pair, 'delta': True, 'data': data}

        await self.con.send_string(f'book {json.dumps(upd)}')
