'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from datetime import timezone, datetime as dt

import bson
from pymongo import AsyncMongoClient

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue


class MongoCallback(BackendQueue):
    def __init__(self, db, host='127.0.0.1', port=27017, uri=None, key=None, none_to=None, numeric_type=str, **kwargs):
        '''
        db: str
            database name
        host: str
            host/ip to connect to. ignored when uri is given
        port: int
            host's port. ignored when uri is given
        uri: str
            a MongoDB connection string
        key: str
            collection name. Defaults to the data type.
        none_to: any
            if not None, convert None values to this value before inserting into MongoDB
        numeric_type: type
            type to convert numeric values to before inserting into MongoDB. Defaults to str
        '''
        self.host = host
        self.port = port
        self.uri = uri
        self.db = db
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.collection = key if key else self.default_key
        self.running = True

    def _client(self) -> AsyncMongoClient:
        if self.uri:
            return AsyncMongoClient(self.uri)
        return AsyncMongoClient(self.host, self.port)

    async def writer(self):
        client = self._client()
        collection = client[self.db][self.collection]
        try:
            while self.running:
                async with self.read_queue() as updates:
                    if not updates:
                        # read_queue yields an empty batch when it consumes the shutdown sentinel
                        continue
                    for index in range(len(updates)):
                        updates[index]['timestamp'] = dt.fromtimestamp(updates[index]['timestamp'], tz=timezone.utc) if updates[index]['timestamp'] else None
                        updates[index]['receipt_timestamp'] = dt.fromtimestamp(updates[index]['receipt_timestamp'], tz=timezone.utc) if updates[index]['receipt_timestamp'] else None

                        if 'book' in updates[index]:
                            delta = 'delta' in updates[index]
                            source = updates[index]['delta'] if delta else updates[index]['book']
                            updates[index] = {
                                'exchange': updates[index]['exchange'],
                                'symbol': updates[index]['symbol'],
                                'timestamp': updates[index]['timestamp'],
                                'receipt_timestamp': updates[index]['receipt_timestamp'],
                                'delta': delta,
                                'bid': bson.encode(source['bid']),
                                'ask': bson.encode(source['ask']),
                            }

                    await collection.insert_many(updates)
        finally:
            await client.close()


class TradeMongo(MongoCallback, BackendCallback):
    default_key = 'trades'


class FundingMongo(MongoCallback, BackendCallback):
    default_key = 'funding'


class BookMongo(MongoCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class TickerMongo(MongoCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestMongo(MongoCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsMongo(MongoCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesMongo(MongoCallback, BackendCallback):
    default_key = 'candles'


class OrderInfoMongo(MongoCallback, BackendCallback):
    default_key = 'order_info'


class TransactionsMongo(MongoCallback, BackendCallback):
    default_key = 'transactions'


class BalancesMongo(MongoCallback, BackendCallback):
    default_key = 'balances'


class FillsMongo(MongoCallback, BackendCallback):
    default_key = 'fills'
