'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
import logging

from redis import asyncio as aioredis
from cryptofeed import _json as json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue, PermanentWriteError


LOG = logging.getLogger(__name__)


class RedisCallback(BackendQueue):
    retryable_exceptions = (aioredis.ConnectionError, aioredis.TimeoutError, aioredis.OutOfMemoryError, aioredis.ReadOnlyError, OSError)

    def __init__(self, host='127.0.0.1', port=6379, socket=None, key=None, none_to='None', numeric_type=float, **kwargs):
        """
        setting key lets you override the prefix on the key used in redis. The defaults are related to the data
        being stored, i.e. trade, funding, etc
        socket: path of a Unix domain socket to connect through instead of host and port
        """
        super().__init__(**kwargs)
        self.redis = f'unix://{socket}' if socket else f'redis://{host}:{port}'
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.conn = None

    async def connect(self):
        if self.conn is None:
            self.conn = aioredis.from_url(self.redis)

    async def close(self):
        if self.conn is not None:
            await self.conn.aclose()
            self.conn = None

    async def _execute(self, pipe) -> list:
        try:
            return await pipe.execute(raise_on_error=False)
        except self.retryable_exceptions:
            raise
        except (aioredis.ResponseError, aioredis.DataError) as e:
            raise PermanentWriteError(str(e)) from e

    async def _run(self, items: list, add) -> list:
        results = [None] * len(items)
        pending = list(range(len(items)))

        for attempt in range(1, self.retry.max_attempts + 1):
            try:
                async with self.conn.pipeline(transaction=False) as pipe:
                    for index in pending:
                        add(pipe, items[index])
                    replies = await self._execute(pipe)
            except self.retryable_exceptions as e:
                if not any(r is not None and not isinstance(r, Exception) for r in results):
                    raise
                replies = [e] * len(pending)

            for index, reply in zip(pending, replies):
                results[index] = reply

            pending = [index for index in pending if isinstance(results[index], self.retryable_exceptions)]
            if not pending:
                break

            if attempt == self.retry.max_attempts:
                LOG.error('%s: redis still rejecting %d of %d commands after %d attempts: %s', type(self).__name__, len(pending), len(items), attempt, results[pending[0]])
                break

            LOG.warning('%s: redis rejected %d of %d commands (%s), retrying them', type(self).__name__, len(pending), len(items), results[pending[0]])
            await asyncio.sleep(self.retry.delay(attempt))

        rejected = [r for r in results if isinstance(r, Exception) and not isinstance(r, self.retryable_exceptions)]
        if rejected:
            LOG.error('%s: redis rejected %d of %d commands in batch. First error: %s', type(self).__name__, len(rejected), len(items), rejected[0])
        return results


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

    async def write_batch(self, batch: list):
        def add(pipe, update):
            pipe.zadd(f"{self.key}-{update['exchange']}-{update['symbol']}", {json.dumps(update): update[self.score_key]}, nx=True)

        results = await self._run(batch, add)
        return sum(count for count in results if not isinstance(count, Exception)), sum(isinstance(r, Exception) for r in results)


class RedisStreamCallback(RedisCallback):
    async def write_batch(self, batch: list):
        def add(pipe, update):
            if 'delta' in update:
                if not isinstance(update['delta'], str):
                    update['delta'] = json.dumps(update['delta'])
            elif 'book' in update:
                if not isinstance(update['book'], str):
                    update['book'] = json.dumps(update['book'])
            elif 'closed' in update:
                if not isinstance(update['closed'], str):
                    update['closed'] = str(update['closed'])

            pipe.xadd(f"{self.key}-{update['exchange']}-{update['symbol']}", update)

        results = await self._run(batch, add)
        discarded = sum(isinstance(r, Exception) for r in results)
        return len(results) - discarded, discarded


class RedisKeyCallback(RedisCallback):

    async def write_batch(self, batch: list):
        latest = {}
        collapsed = defaultdict(int)

        for update in batch:
            key = f"{self.key}-{update['exchange']}-{update['symbol']}"
            latest[key] = update
            collapsed[key] += 1

        def add(pipe, item):
            key, update = item
            pipe.set(key, json.dumps(update))

        results = await self._run(list(latest.items()), add)
        if not any(isinstance(r, Exception) for r in results):
            return None

        stored = sum(collapsed[key] for key, result in zip(latest, results) if not isinstance(result, Exception))
        return stored, len(batch) - stored


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


class BookSnapshotRedisKey(RedisKeyCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshot_interval=1000, **kwargs):
        self.snapshots_only = True
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


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
