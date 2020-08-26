'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import bson
import motor.motor_asyncio

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback, BackendLiquidationsCallback)


class MongoCallback:
    def __init__(self, db, host='127.0.0.1', port=27017, key=None, numeric_type=str, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.collection = key if key else self.default_key

    async def write(self, feed: str, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        d = {'feed': feed, 'pair': pair, 'timestamp': timestamp, 'receipt_timestamp': timestamp, 'delta': data['delta'], 'bid': bson.BSON.encode(data['bid']), 'ask': bson.BSON.encode(data['ask'])}
        await self.db[self.collection].insert_one(d)


class TradeMongo(MongoCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingMongo(MongoCallback, BackendFundingCallback):
    default_key = 'funding'


class BookMongo(MongoCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaMongo(MongoCallback, BackendBookDeltaCallback):
    default_key = 'book'


class TickerMongo(MongoCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestMongo(MongoCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsMongo(MongoCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'
