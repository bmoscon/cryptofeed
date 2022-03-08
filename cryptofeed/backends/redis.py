'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio

import aioredis
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue


class RedisCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, none_to='None', numeric_type=float, writer_interval=0.01, **kwargs):
        """
        setting key lets you override the prefix on the
        key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc

        writer_interval: float
            the frequency writer sleeps when there is nothing in the queue.
            0 consumes a lot of CPU, while large interval puts pressure on queue.
        """
        prefix = 'redis://'
        if socket:
            prefix = 'unix://'

        self.redis = aioredis.from_url(f"{prefix}{host}:{port}")
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.running = True
        self.exited = False
        self.writer_interval = writer_interval

    async def stop(self):
        self.running = False
        while not self.exited:
            await asyncio.sleep(0.1)


class RedisZSetCallback(RedisCallback):
    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, numeric_type=float, score_key='timestamp', **kwargs):
        """
        score_key: str
            the value at this key will be used to store the data in the ZSet in redis. The
            default is timestamp. If you wish to look up the data by a different value,
            use this to change it. It must be a numeric value.
        """
        self.score_key = score_key
        super().__init__(host=host, port=port, socket=socket, key=key, numeric_type=numeric_type, **kwargs)

    async def write(self, data: dict):
        score = data[self.score_key]
        await self.queue.put({'score': score, 'data': data})

    async def writer(self):
        while self.running:

            count = self.queue.qsize()
            if count == 0:
                await asyncio.sleep(self.writer_interval)
            elif count > 1:
                async with self.read_many_queue(count) as updates:
                    async with self.redis.pipeline(transaction=False) as pipe:
                        for update in updates:
                            pipe = pipe.zadd(f"{self.key}-{update['data']['exchange']}-{update['data']['symbol']}", {json.dumps(update['data']): update['score']}, nx=True)
                        await pipe.execute()
            else:
                async with self.read_queue() as update:
                    await self.redis.zadd(f"{self.key}-{update['data']['exchange']}-{update['data']['symbol']}", {json.dumps(update['data']): update['score']}, nx=True)

        await self.redis.close()
        await self.redis.connection_pool.disconnect()
        self.exited = True


class RedisStreamCallback(RedisCallback):
    async def write(self, data: dict):
        await self.queue.put(data)

    async def writer(self):
        while self.running:

            count = self.queue.qsize()
            if count == 0:
                await asyncio.sleep(self.writer_interval)
            elif count > 1:
                async with self.read_many_queue(count) as updates:
                    async with self.redis.pipeline(transaction=False) as pipe:
                        for update in updates:
                            pipe = pipe.xadd(f"{self.key}-{update['exchange']}-{update['symbol']}", update)
                        await pipe.execute()
            else:
                async with self.read_queue() as update:
                    await self.redis.xadd(f"{self.key}-{update['exchange']}-{update['symbol']}", update)

        await self.redis.close()
        await self.redis.connection_pool.disconnect()
        self.exited = True


class TradeRedis(RedisZSetCallback, BackendCallback):
    default_key = 'trades'


class TradeStream(RedisStreamCallback, BackendCallback):
    default_key = 'trades'


class FundingRedis(RedisZSetCallback, BackendCallback):
    default_key = 'funding'


class FundingStream(RedisStreamCallback, BackendCallback):
    default_key = 'funding'


class BookRedis(RedisZSetCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, score_key='receipt_timestamp', **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, score_key=score_key, **kwargs)


class BookStream(RedisStreamCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)

    async def write(self, data: dict):
        if 'delta' in data:
            data['delta'] = json.dumps(data['delta'])
        elif 'book' in data:
            data['book'] = json.dumps(data['book'])

        await super().write(data)


class TickerRedis(RedisZSetCallback, BackendCallback):
    default_key = 'ticker'


class TickerStream(RedisStreamCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestRedis(RedisZSetCallback, BackendCallback):
    default_key = 'open_interest'


class OpenInterestStream(RedisStreamCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsRedis(RedisZSetCallback, BackendCallback):
    default_key = 'liquidations'


class LiquidationsStream(RedisStreamCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesRedis(RedisZSetCallback, BackendCallback):
    default_key = 'candles'


class CandlesStream(RedisStreamCallback, BackendCallback):
    default_key = 'candles'

    async def write(self, data: dict):
        data['closed'] = str(data['closed'])
        await super().write(data)
