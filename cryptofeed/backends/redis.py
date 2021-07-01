'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import aioredis
from yapic import json

from cryptofeed.backends.backend import (BackendQueue, BackendBookCallback, BackendCandlesCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback)


def trades_none_to_str(data):
    if data['order_type'] is None:
        data['order_type'] = 'None'
    if data['id'] is None:
        data['id'] = 'None'


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

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        score = data[self.score_key]
        data = json.dumps(data)
        await self.queue.put({'feed': feed, 'symbol': symbol, 'score': score, 'data': data})

    async def writer(self):
        while True:

            count = self.queue.qsize()
            if count > 1:
                async with self.read_many_queue(count) as updates:
                    async with self.redis.pipeline(transaction=False) as pipe:
                        for update in updates:
                            pipe = pipe.zadd(f"{self.key}-{update['feed']}-{update['symbol']}", {update['data']: update['score']}, nx=True)
                        await pipe.execute()
            else:
                async with self.read_queue() as update:
                    await self.redis.zadd(f"{self.key}-{update['feed']}-{update['symbol']}", {update['data']: update['score']}, nx=True)


class RedisStreamCallback(RedisCallback):
    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await self.queue.put({'feed': feed, 'symbol': symbol, 'data': data})

    async def writer(self):
        while True:

            count = self.queue.qsize()
            if count > 1:
                async with self.read_many_queue(count) as updates:
                    async with self.redis.pipeline(transaction=False) as pipe:
                        for update in updates:
                            pipe = pipe.xadd(f"{self.key}-{update['feed']}-{update['symbol']}", update['data'])
                        await pipe.execute()
            else:
                async with self.read_queue() as update:
                    await self.redis.xadd(f"{self.key}-{update['feed']}-{update['symbol']}", update['data'])


class TradeRedis(RedisZSetCallback, BackendTradeCallback):
    default_key = 'trades'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        trades_none_to_str(data)
        await super().write(feed, symbol, timestamp, receipt_timestamp, data)


class TradeStream(RedisStreamCallback, BackendTradeCallback):
    default_key = 'trades'

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        trades_none_to_str(data)
        await super().write(feed, symbol, timestamp, receipt_timestamp, data)


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

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        data['delta'] = 'False'
        data['bid'] = json.dumps(data['bid'])
        data['ask'] = json.dumps(data['ask'])

        await super().write(feed, symbol, timestamp, receipt_timestamp, data)


class BookDeltaStream(RedisStreamCallback, BackendBookDeltaCallback):
    default_key = 'book'

    async def write(self, feed: str, symbol: str, timestamp: str, receipt_timestamp: float, data: dict):
        data['delta'] = 'True'
        data['bid'] = json.dumps(data['bid'])
        data['ask'] = json.dumps(data['ask'])

        await super().write(feed, symbol, timestamp, receipt_timestamp, data)


class TickerRedis(RedisZSetCallback, BackendTickerCallback):
    default_key = 'ticker'


class TickerStream(RedisStreamCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestRedis(RedisZSetCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class OpenInterestStream(RedisStreamCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsRedis(RedisZSetCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class LiquidationsStream(RedisStreamCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoRedis(RedisZSetCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class MarketInfoStream(RedisStreamCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class CandlesRedis(RedisZSetCallback, BackendCandlesCallback):
    default_key = 'candles'


class CandlesStream(RedisStreamCallback, BackendCandlesCallback):
    default_key = 'candles'
