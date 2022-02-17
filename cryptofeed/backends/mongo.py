'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from datetime import timezone, datetime as dt

import bson
import motor.motor_asyncio

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue


class MongoCallback(BackendQueue):
    def __init__(self, db, host='127.0.0.1', port=27017, key=None, none_to=None, numeric_type=str, writer_interval=0.01, **kwargs):
        self.conn = motor.motor_asyncio.AsyncIOMotorClient(host, port)
        self.db = self.conn[db]
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.collection = key if key else self.default_key
        self.running = True
        self.exited = False
        self.writer_interval = writer_interval

    async def stop(self):
        self.running = False
        while not self.exited:
            await asyncio.sleep(0.1)

    async def write(self, data: dict):
        data['timestamp'] = dt.fromtimestamp(data['timestamp'], tz=timezone.utc) if data['timestamp'] else None
        data['receipt_timestamp'] = dt.fromtimestamp(data['receipt_timestamp'], tz=timezone.utc) if data['receipt_timestamp'] else None

        if 'book' in data:
            data = {'exchange': data['exchange'], 'symbol': data['symbol'], 'timestamp': data['timestamp'], 'receipt_timestamp': data['receipt_timestamp'], 'delta': 'delta' in data, 'bid': bson.BSON.encode(data['book']['bid'] if 'delta' not in data else data['delta']['bid']), 'ask': bson.BSON.encode(data['book']['ask'] if 'delta' not in data else data['delta']['ask'])}

        await self.queue.put(data)

    async def writer(self):
        while self.running:
            count = self.queue.qsize()
            if count == 0:
                await asyncio.sleep(self.writer_interval)
            elif count > 1:
                async with self.read_many_queue(count) as updates:
                    await self.db[self.collection].insert_many(updates)
            else:
                async with self.read_queue() as update:
                    await self.db[self.collection].insert_one(update)
        self.exited = True


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
