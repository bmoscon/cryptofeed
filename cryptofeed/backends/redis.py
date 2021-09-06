'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import aioredis
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue


def trades_none_to_str(data):
    data['type'] = str(data['type'])
    data['id'] = str(data['id'])


class RedisCallback(BackendQueue):
    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, numeric_type=float, **kwargs):
        """
        setting key lets you override the prefix on the
        key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc
        """
        prefix = 'redis://'
        if socket:
            prefix = 'unix://'

        self.redis = aioredis.from_url(f"{prefix}{host}:{port}")
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.running = True
        self.exited = False

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
                await asyncio.sleep(0)
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
                await asyncio.sleep(0)
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

    async def write(self, data):
        trades_none_to_str(data)
        await super().write(data)


class TradeStream(RedisStreamCallback, BackendCallback):
    default_key = 'trades'

    async def write(self, data):
        trades_none_to_str(data)
        await super().write(data)


class FundingRedis(RedisZSetCallback, BackendCallback):
    default_key = 'funding'


class FundingStream(RedisStreamCallback, BackendCallback):
    default_key = 'funding'


class BookRedis(RedisZSetCallback, BackendBookCallback):
    default_key = 'book'

    async def write(self, data: dict):
        if data['delta'] is None:
            data['delta'] = 'None'
        if data['timestamp'] is None:
            data['timestamp'] = 'None'
        await super().write(data)


class BookStream(RedisStreamCallback, BackendBookCallback):
    default_key = 'book'

    async def write(self, data: dict):
        if 'delta' in data:
            data['delta'] = json.dumps(data['delta'])
        elif 'book' in data:
            data['book'] = json.dumps(data['book'])

        if data['timestamp'] is None:
            data['timestamp'] = 'None'
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
