'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from collections import Counter

from aiohttp import ClientResponseError

from cryptofeed.connection import retry_after
from cryptofeed.defines import L2_BOOK


LOG = logging.getLogger(__name__)


class _BookSync:
    __slots__ = ('conn', 'buffer', 'task', 'result', 'started')

    def __init__(self, conn: str, update, receipt: float):
        self.conn = conn
        self.buffer = [(update, receipt)]
        self.task = None
        self.result = None
        self.started = time.time()


class SnapshotSync:
    SNAPSHOT_CONCURRENCY = 5
    SNAPSHOT_TIMEOUT = 30.0
    SNAPSHOT_HEADERS = None
    BOOK_BUFFER_LIMIT = 2000
    SNAPSHOT_RETRY_DELAY = 1.0
    SNAPSHOT_RETRY_MAX = 60.0
    RATE_LIMIT_WAIT = 60.0

    def _sync_init(self):
        self._syncing = {}
        self._ready = set()
        self._snapshot_slots = None
        self.book_sync_stats = Counter()

    def _rest_weight(self):
        return None

    def _cancel_syncs(self, conn: str = None):
        for pair, sync in list(self._syncing.items()):
            if conn is None or sync.conn == conn:
                del self._syncing[pair]
                self._ready.discard(pair)
                if sync.task is not None:
                    sync.task.cancel()

    async def shutdown(self):
        self._cancel_syncs()
        return await super().shutdown()

    def _buffer_update(self, pair: str, std_pair: str, msg, conn, receipt: float):
        sync = self._syncing.get(std_pair)
        if sync is None:
            sync = self._syncing[std_pair] = _BookSync(getattr(conn, 'uuid', None), msg, receipt)
            self._start_fetch(pair, std_pair, sync)
        elif len(sync.buffer) < self.BOOK_BUFFER_LIMIT:
            sync.buffer.append((msg, receipt))
        else:
            self.book_sync_stats['buffer_overflows'] += 1
            LOG.warning('%s: %s buffered %d updates waiting for its snapshot - restarting its sync', self.id, std_pair, len(sync.buffer))
            sync.task.cancel()
            sync.buffer, sync.started = [(msg, receipt)], time.time()
            self._start_fetch(pair, std_pair, sync)

    def _start_fetch(self, pair: str, std_pair: str, sync: _BookSync):
        sync.result = None
        self._ready.discard(std_pair)
        sync.task = asyncio.create_task(self._fetch_snapshot(pair, std_pair, sync), name=f'{self.id}.snapshot.{pair}')

    async def _fetch_snapshot(self, pair: str, std_pair: str, sync: _BookSync):
        if self._snapshot_slots is None:
            self._snapshot_slots = asyncio.Semaphore(self.SNAPSHOT_CONCURRENCY)

        weights = self._rest_weight()
        delay = self.SNAPSHOT_RETRY_DELAY

        while True:
            try:
                async with self._snapshot_slots:
                    if weights is not None:
                        await weights.acquire(self._snapshot_weight())
                    headers = {}
                    try:
                        async with asyncio.timeout(self.SNAPSHOT_TIMEOUT):
                            response = await self.http_conn.read(self._snapshot_url(pair), header=self.SNAPSHOT_HEADERS, headers_out=headers)
                    finally:
                        if weights is not None:
                            weights.observe(headers)
                received = time.time()
                book = self._parse_snapshot(std_pair, response)
            except Exception as e:
                self.book_sync_stats['snapshot_failures'] += 1

                if isinstance(e, ClientResponseError) and e.status in (418, 429):
                    wait = retry_after(e.headers or {}, self.RATE_LIMIT_WAIT)
                    LOG.warning('%s: %s snapshot request hit the rate limit (%d) - pausing snapshots for %.0fs', self.id, std_pair, e.status, wait)
                    if weights is not None:
                        weights.block(wait)
                    else:
                        await asyncio.sleep(wait)
                else:
                    LOG.warning('%s: %s snapshot request failed: %r - retrying in %.0fs', self.id, std_pair, e, delay)
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.SNAPSHOT_RETRY_MAX)
                continue

            if self._syncing.get(std_pair) is sync:
                sync.result = (book, received)
                self._ready.add(std_pair)
            return

    async def _install_snapshots(self, conn):
        uuid = getattr(conn, 'uuid', None)
        for std_pair in [pair for pair, sync in self._syncing.items() if pair in self._ready and sync.conn == uuid]:
            self._ready.discard(std_pair)
            sync = self._syncing[std_pair]
            book, received = sync.result
            sequence = book.sequence_number
            covered = 0

            while covered < len(sync.buffer) and self._covered(sequence, sync.buffer[covered][0]):
                covered += 1

            pair = self.std_symbol_to_exchange_symbol(std_pair)
            if covered < len(sync.buffer) and not self._bridges(sequence, sync.buffer[covered][0]):
                self.book_sync_stats['stale_snapshots'] += 1
                self._start_fetch(pair, std_pair, sync)
                continue

            del self._syncing[std_pair]
            self.book_sync_stats['snapshots'] += 1
            self.book_sync_stats['sync_discards'] += covered

            LOG.debug('%s: %s book live %.2fs after its first update (%d buffered, %d covered by the snapshot)', self.id, std_pair, received - sync.started, len(sync.buffer), covered)

            self._start_book(std_pair, book)
            await self.book_callback(L2_BOOK, book, received, timestamp=book.timestamp, raw=book.raw, sequence_number=sequence)

            for msg, receipt in sync.buffer[covered:]:
                await self._apply_buffered(pair, msg, receipt, conn)
