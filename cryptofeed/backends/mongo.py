'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from datetime import timezone, datetime as dt

import bson
from bson.errors import BSONError
from pymongo import AsyncMongoClient
from pymongo.errors import BulkWriteError, ConnectionFailure, ExecutionTimeout

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue, PermanentWriteError


DUPLICATE_KEY = 11000
DEFAULT_CLIENT_OPTIONS = {'serverSelectionTimeoutMS': 5000}


class MongoCallback(BackendQueue):
    retryable_exceptions = (ConnectionFailure, ExecutionTimeout, OSError)

    def __init__(self, db, host='127.0.0.1', port=27017, uri=None, key=None, none_to=None, numeric_type=str,
                 client_options=None, **kwargs):
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
        client_options: dict
            passed straight to pymongo's AsyncMongoClient - username/password, tls,
            connectTimeoutMS, serverSelectionTimeoutMS and anything else the driver accepts.
            serverSelectionTimeoutMS defaults to 5000 here rather than pymongo's 30000; an option
            named in `uri` is left alone, because pymongo lets a keyword argument override the
            connection string and a silent default must not beat what the caller wrote.
        '''
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.uri = uri
        self.client_options = dict(client_options) if client_options else {}
        provided = {name.lower() for name in self.client_options}
        for name, value in DEFAULT_CLIENT_OPTIONS.items():
            if name.lower() not in provided and not (uri and name.lower() in uri.lower()):
                self.client_options[name] = value
        self.db = db
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.collection = key if key else self.default_key
        self.client = None
        self.collection_handle = None

    def _client(self) -> AsyncMongoClient:
        if self.uri:
            return AsyncMongoClient(self.uri, **self.client_options)
        return AsyncMongoClient(self.host, self.port, **self.client_options)

    async def connect(self):
        if self.client is None:
            self.client = self._client()
            self.collection_handle = self.client[self.db][self.collection]

    @staticmethod
    def _datetime(value):
        if not value:
            return None
        if isinstance(value, dt):
            return value
        return dt.fromtimestamp(value, tz=timezone.utc)

    def _document(self, update: dict) -> dict:
        update['timestamp'] = self._datetime(update['timestamp'])
        update['receipt_timestamp'] = self._datetime(update['receipt_timestamp'])

        if 'book' in update:
            delta = 'delta' in update
            source = update['delta'] if delta else update['book']
            return {
                'exchange': update['exchange'],
                'symbol': update['symbol'],
                'timestamp': update['timestamp'],
                'receipt_timestamp': update['receipt_timestamp'],
                'delta': delta,
                'bid': bson.encode(source['bid']),
                'ask': bson.encode(source['ask']),
            }
        return update

    async def write_batch(self, batch: list):
        for index, update in enumerate(batch):
            batch[index] = self._document(update)

        try:
            await self.collection_handle.insert_many(batch, ordered=False)
        except BulkWriteError as e:
            errors = e.details.get('writeErrors', [])
            duplicates = [error for error in errors if error.get('code') == DUPLICATE_KEY]
            if len(duplicates) < len(errors):
                raise PermanentWriteError(str(e)) from e
            return len(batch) - len(duplicates)
        except BSONError as e:
            raise PermanentWriteError(str(e)) from e

    async def close(self):
        if self.client is not None:
            await self.client.close()
            self.client = None
            self.collection_handle = None


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
