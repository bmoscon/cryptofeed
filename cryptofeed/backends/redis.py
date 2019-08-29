'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import time
import json

import aioredis

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class RedisCallback:
    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, numeric_type=str, **kwargs):
        """
        setting key lets you override the prefix on the
        key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc
        """
        self.redis = None
        self.key = key
        self.numeric_type = numeric_type

        self.conn_str = socket if socket else f'redis://{host}:{port}'

    async def connect(self):
        if self.redis is None:
            self.redis = await aioredis.create_redis_pool(self.conn_str)

class TradeRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'trades'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self.connect()

        data = json.dumps({'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                           'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)})

        await self.redis.zadd(f"{self.key}-{feed}-{pair}", timestamp, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class TradeStream(TradeRedis):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self.connect()

        data = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}

        if data['id'] is None:
            data['id'] = ''
        await self.redis.xadd(f"{self.key}-{feed}-{pair}", data)


class FundingRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'funding'

    async def __call__(self, *, feed, pair, **kwargs):
        await self.connect()

        timestamp = kwargs.get('timestamp', None)

        if timestamp is None:
            timestamp = time.time()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])

        data = json.dumps(kwargs)

        await self.redis.zadd(f"{self.key}-{feed}-{pair}", timestamp, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class FundingStream(FundingRedis):
    async def __call__(self, *, feed, pair, **kwargs):
        await self.connect()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])

        await self.redis.xadd(f"{self.key}-{feed}-{pair}", kwargs)


class BookRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'book'
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        ts = time.time()
        await self.connect()

        data = {'timestamp': timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, self.depth, convert=self.numeric_type)

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]

        data = json.dumps(data)
        await self.redis.zadd(f"{self.key}-{feed}-{pair}", ts, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class BookDeltaRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'book'

    async def __call__(self, *, feed, pair, delta, timestamp):
        ts = time.time()
        await self.connect()

        data = {'timestamp': timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)
        data = json.dumps(data)
        await self.redis.zadd(f"{self.key}-{feed}-{pair}", ts, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class BookStream(BookRedis):
    async def __call__(self, *, feed, pair, book, timestamp):
        await self.connect()

        data = {'timestamp': timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, self.depth, convert=self.numeric_type)

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]

        data = json.dumps(data)
        await self.redis.xadd(f"{self.key}-{feed}-{pair}", {'data': data})


class BookDeltaStream(BookRedis):
    async def __call__(self, *, feed, pair, delta, timestamp):
        await self.connect()

        data = {'timestamp': timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)

        data = json.dumps(data)
        await self.redis.xadd(f"{self.key}-{feed}-{pair}", {'data': data})
