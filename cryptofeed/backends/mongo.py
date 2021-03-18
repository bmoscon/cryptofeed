'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import bson
import motor.motor_asyncio


from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)


class MongoCallback:
    def __init__(self, db, host='127.0.0.1', port=27017, key=None, numeric_type=str, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.collection = key if key else self.default_key

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        if 'delta' in data:
            d = {'feed': feed, 'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': data['delta'], 'bid': bson.BSON.encode(data['bid']), 'ask': bson.BSON.encode(data['ask'])}
            await self.db[self.collection].insert_one(d)
        else:
            await self.db[self.collection].insert_one(data)


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


class MarketInfoMongo(MongoCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsMongo(MongoCallback, BackendTransactionsCallback):
    default_key = 'transactions'


class CandlesMongo(MongoCallback, BackendCandlesCallback):
    default_key = 'candles'
