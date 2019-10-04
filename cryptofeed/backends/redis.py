'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import time
import json

import aioredis

from cryptofeed.backends.backend import Backend
from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class RedisCallback(Backend):
    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, numeric_type=float, **kwargs):
        """
        setting key lets you override the prefix on the
        key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc
        """
        self.redis = None
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.conn_str = socket if socket else f'redis://{host}:{port}'


class RedisZSetCallback(RedisCallback):
    async def write(self, feed: str, pair: str, timestamp: float, data: str):
        if self.redis is None:
            self.redis = await aioredis.create_redis_pool(self.conn_str)
        await self.redis.zadd(f"{self.key}-{feed}-{pair}", timestamp, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class RedisStreamCallback(RedisCallback):
    async def write(self, feed: str, pair: str, data: str):
        if self.redis is None:
            self.redis = await aioredis.create_redis_pool(self.conn_str)
        await self.redis.xadd(f"{self.key}-{feed}-{pair}", data)


class TradeRedis(RedisZSetCallback):
    default_key = 'trades'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        data = json.dumps(self.trade(feed, pair, side, amount, price, order_id, timestamp, self.numeric_type))
        await self.write(feed, pair, timestamp, data)


class TradeStream(RedisStreamCallback):
    default_key = 'trades'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        data = self.trade(feed, pair, side, amount, price, order_id, timestamp, self.numeric_type)
        if data['id'] is None:
            data['id'] = ''
        await self.write(feed, pair, data)


class FundingRedis(RedisZSetCallback):
    default_key = 'funding'

    async def __call__(self, *, feed, pair, **kwargs):
        timestamp = kwargs.get('timestamp', None)
        if timestamp is None:
            timestamp = time.time()

        data = json.dumps(self.funding(self.numeric_type, kwargs))
        await self.write(feed, pair, timestamp, data)


class FundingStream(RedisStreamCallback):
    default_key = 'funding'

    async def __call__(self, *, feed, pair, **kwargs):
        data = json.dumps(self.funding(self.numeric_type, kwargs))
        await self.write(feed, pair, data)


class BookRedis(RedisZSetCallback):
    default_key = 'book'

    async def __call__(self, *, feed, pair, book, timestamp):
        data = json.dumps(self.book(book, timestamp, self.numeric_type))
        await self.write(feed, pair, timestamp, data)


class BookDeltaRedis(BookRedis):
    async def __call__(self, *, feed, pair, delta, timestamp):
        data = json.dumps(self.book_delta(delta, timestamp, self.numeric_type))
        await self.write(feed, pair, timestamp, data)


class BookStream(RedisStreamCallback):
    default_key = 'book'

    async def __call__(self, *, feed, pair, book, timestamp):
        data = json.dumps(self.book(book, timestamp, self.numeric_type))
        await self.write(feed, pair, data)


class BookDeltaStream(BookStream):
    async def __call__(self, *, feed, pair, delta, timestamp):
        data = json.dumps(self.book_delta(delta, timestamp, self.numeric_type))
        await self.write(feed, pair, data)


class TickerRedis(RedisZSetCallback):
    default_key = 'ticker'

    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float):
        data = json.dumps(self.ticker(feed, pair, bid, ask, timestamp, self.numeric_type))
        await self.write(feed, pair, timestamp, data)


class TickerStream(RedisStreamCallback):
    default_key = 'ticker'

    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float):
        data = self.ticker(feed, pair, bid, ask, timestamp, self.numeric_type)
        await self.write(feed, pair, data)
