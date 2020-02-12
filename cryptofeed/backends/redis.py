'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json

import aioredis

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendTickerCallback, BackendTradeCallback, BackendFundingCallback, BackendOpenInterestCallback


class RedisCallback:
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
    async def write(self, feed: str, pair: str, timestamp: float, data: dict):
        data = json.dumps(data)
        if self.redis is None:
            self.redis = await aioredis.create_redis_pool(self.conn_str)
        await self.redis.zadd(f"{self.key}-{feed}-{pair}", timestamp, data, exist=self.redis.ZSET_IF_NOT_EXIST)


class RedisStreamCallback(RedisCallback):
    async def write(self, feed: str, pair: str, timestamp: float, data: dict):
        if self.redis is None:
            self.redis = await aioredis.create_redis_pool(self.conn_str)
        await self.redis.xadd(f"{self.key}-{feed}-{pair}", data)


class TradeRedis(RedisZSetCallback, BackendTradeCallback):
    default_key = 'trades'


class TradeStream(RedisStreamCallback, BackendTradeCallback):
    default_key = 'trades'

class FundingRedis(RedisZSetCallback, BackendFundingCallback):
    default_key = 'funding'


class FundingStream(RedisStreamCallback, BackendFundingCallback):
    default_key = 'funding'


class BookRedis(RedisZSetCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaRedis(RedisZSetCallback, BackendBookDeltaCallback):
    default_key = 'book'


class BookStream(RedisStreamCallback, BackendBookCallback):
    default_key = 'book'

    async def write(self, feed, pair, timestamp, data):
        data = {'data': json.dumps(data)}
        await super().write(feed, pair, timestamp, data)


class BookDeltaStream(RedisStreamCallback, BackendBookDeltaCallback):
    default_key = 'book'

    async def write(self, feed, pair, timestamp, data):
        data = {'data': json.dumps(data)}
        await super().write(feed, pair, timestamp, data)


class TickerRedis(RedisZSetCallback, BackendTickerCallback):
    default_key = 'ticker'


class TickerStream(RedisStreamCallback, BackendTickerCallback):
    default_key = 'ticker'
    

class OpenInterestRedis(RedisZSetCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class OpenInterestStream(RedisStreamCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'
