from decimal import Decimal
import time
import json

import aioredis

from cryptofeed.standards import timestamp_normalize


class RedisCallback:
    def __init__(self, host='127.0.0.1', port=6379):
        self.host = host
        self.port = port
        self.redis = None


class TradeRedis(RedisCallback):
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

        await self.redis.execute('ZADD', "{}-{}".format(feed, pair), ts, data)
