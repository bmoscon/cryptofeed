'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import bson
import motor.motor_asyncio


from cryptofeed.backends.backend import BackendBookCallback, BackendCallback


class MongoCallback:
    def __init__(self, db, host='127.0.0.1', port=27017, key=None, numeric_type=str, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.collection = key if key else self.default_key

    async def write(self, data: dict):
        if 'delta' in data:
            d = {'exchange': data['exchange'], 'symbol': data['symbol'], 'timestamp': data['timestamp'], 'receipt_timestamp': data['receipt_timestamp'], 'delta': data['delta'], 'bid': bson.BSON.encode(data['bid']), 'ask': bson.BSON.encode(data['ask'])}
            await self.db[self.collection].insert_one(d)
        else:
            await self.db[self.collection].insert_one(data)


class TradeMongo(MongoCallback, BackendCallback):
    default_key = 'trades'


class FundingMongo(MongoCallback, BackendCallback):
    default_key = 'funding'


class BookMongo(MongoCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, **kwargs):
        self.snapshots_only = snapshots_only
        super().__init__(*args, **kwargs)


class TickerMongo(MongoCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestMongo(MongoCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsMongo(MongoCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesMongo(MongoCallback, BackendCallback):
    default_key = 'candles'
