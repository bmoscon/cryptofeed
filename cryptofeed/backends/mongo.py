'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import motor.motor_asyncio

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class MongoCallback:
    def __init__(self, db, host='127.0.0.1', port=27017, collection=None, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.collection = collection


class TradeMongo(MongoCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.collection is None:
            self.collection = 'trades'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        data = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                'side': side, 'amount': float(amount), 'price': float(price)}

        await self.db[self.collection].insert_one(data)


class FundingMongo(MongoCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.collection is None:
            self.collection = 'funding'

    async def __call__(self, *, feed, pair, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        await self.db[self.collection].insert_one(kwargs)


class BookMongo(MongoCallback):
    """
    Because periods cannot be in keys in documents in mongo, the prices in L2/L3 books
    are converted to integers in the following way:
    price is * 10000 and truncated
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.collection is None:
            self.collection = 'book'
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {'timestamp': timestamp, 'feed': feed, 'pair': pair, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, self.depth, convert=lambda x: str(int(x * 10000)))

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]

        await self.db[self.collection].insert_one(data)


class BookDeltaMongo(MongoCallback):
    """
    Because periods cannot be in keys in documents in mongo, the prices in L2/L3 books
    are converted to integers in the following way:
    price is * 10000 and truncated
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.collection is None:
            self.collection = 'book'

    async def __call__(self, *, feed, pair, delta, timestamp):
        data = {'timestamp': timestamp, 'feed': feed, 'pair': pair, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=lambda x: str(int(x * 10000)))

        await self.db[self.collection].insert_one(data)
