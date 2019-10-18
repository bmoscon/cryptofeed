'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import motor.motor_asyncio

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback


class MongoCallback:
    def __init__(self, db, host='127.0.0.1', port=27017, key=None, numeric_type=float, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.collection = key if key else self.default_key

    async def write(self, feed: str, pair: str, timestamp: float, data: dict):
        await self.db[self.collection].insert_one(data)


class TradeMongo(MongoCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingMongo(MongoCallback, BackendFundingCallback):
   default_key = 'funding'


class BookMongo(MongoCallback, BackendBookCallback):
    """
    Because periods (decimal point) cannot be in keys in documents in mongo, the prices in L2/L3 books
    are converted to integers in the following way:
    price is * 10000 and truncated
    """
    default_key = 'book'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.numeric_type = lambda x: str(int(x * 10000))


class BookDeltaMongo(MongoCallback, BackendBookDeltaCallback):
    """
    Because periods (decimal point) cannot be in keys in documents in mongo, the prices in L2/L3 books
    are converted to integers in the following way:
    price is * 10000 and truncated
    """
    default_key = 'book'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.numeric_type = lambda x: str(int(x * 10000))


class TickerMongo(MongoCallback, BackendTickerCallback):
    default_key = 'ticker'
