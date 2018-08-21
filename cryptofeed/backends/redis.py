from decimal import Decimal
import time
import json

import aioredis

from cryptofeed.standards import timestamp_normalize


class RedisCallback:
    def __init__(self, host='127.0.0.1', port=6379, key=None):
        """
        setting key lets you override the prefix on the
        key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc
        """
        self.host = host
        self.port = port
        self.redis = None
        self.key = key


class TradeRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'trade'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, id=None, timestamp=None):
        if self.redis is None:
            self.redis = await aioredis.create_redis('redis://{}:{}'.format(self.host, self.port))
        ts = None
        if timestamp is None:
            timestamp = time.time()
            ts = timestamp
        else:
            ts = timestamp_normalize(feed, timestamp)

        data = json.dumps({'feed': feed, 'pair': pair, 'id': id, 'timestamp': timestamp, 'side': side, 'amount': float(amount), 'price': float(price)})

        await self.redis.execute('ZADD', "{}-{}-{}".format(self.key, feed, pair), ts, data)


class FundingRedis(RedisCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = 'funding'

    async def __call__(self, *, feed, pair, timestamp, interval, rate, rate_daily):
        if self.redis is None:
            self.redis = await aioredis.create_redis('redis://{}:{}'.format(self.host, self.port))
        ts = None
        if timestamp is None:
            timestamp = time.time()
            ts = timestamp
        else:
            ts = timestamp_normalize(feed, timestamp)

        data = json.dumps({'feed': feed, 'pair': pair, 'timestamp': timestamp, 'interval': interval, 'rate': float(rate), 'rate_daily': float(rate_daily)})

        await self.redis.execute('ZADD', "{}-{}-{}".format(self.key, feed, pair), ts, data)
