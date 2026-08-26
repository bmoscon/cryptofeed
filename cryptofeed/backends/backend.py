'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import random
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Literal, Optional


LOG = logging.getLogger('cryptofeed.backends')


class PermanentWriteError(Exception):
    '''raised when the data is truly un-writeable by the backend'''


class _ShutdownSentinel:
    __slots__ = ()

    def __repr__(self):
        return '* shutdown sentinel *'


SHUTDOWN_SENTINEL = _ShutdownSentinel()


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base: float = 0.5
    jitter: bool = True

    def delay(self, attempt: int) -> float:
        d = self.base * (2 ** (attempt - 1))
        if self.jitter:
            d *= random.uniform(0.5, 1.5)
        return d


@dataclass(frozen=True)
class BackendStats:
    qsize: int
    written: int
    batches: int
    dropped_overflow: int
    dropped_failed: int
    conflicts: int
    retries: int
    last_error: Optional[str]
    last_write_ts: Optional[float]
    hand_off: bool = False

    @property
    def delivered(self) -> int:
        return self.written + self.conflicts


class BackendQueue:
    hand_off = False
    max_depth = 10_000
    overflow = 'drop_oldest'
    batch_max = 500
    batch_interval = 0.5
    flush_deadline = 5.0
    retry = RetryPolicy()
    retryable_exceptions: tuple = ()
    SENTINEL_TIMEOUT = 1.0
    BLOCK_POLL = 0.25
    FAILURE_LEVEL = logging.ERROR

    def __init__(self, *,
                 max_depth: Optional[int] = None,
                 overflow: Optional[Literal['block', 'drop_oldest', 'drop_new']] = None,
                 batch_max: Optional[int] = None,
                 batch_interval: Optional[float] = None,
                 retry: Optional[RetryPolicy] = None,
                 flush_deadline: Optional[float] = None):
        if overflow is not None and overflow not in ('block', 'drop_oldest', 'drop_new'):
            raise ValueError(f"overflow must be 'block', 'drop_oldest' or 'drop_new', not {overflow!r}")
        for name, value in (('max_depth', max_depth), ('overflow', overflow),
                            ('batch_max', batch_max), ('batch_interval', batch_interval),
                            ('retry', retry), ('flush_deadline', flush_deadline)):
            if value is not None:
                setattr(self, name, value)
        self._init_state()

    def _init_state(self):
        if not hasattr(self, '_written'):
            self._written = 0
            self._batches = 0
            self._dropped_overflow = 0
            self._dropped_failed = 0
            self._conflicts = 0
            self._retries = 0
            self._last_error = None
            self._last_write_ts = None
            self._failing = False
            self._failed_batches = 0
            self._orphaned = False
            self._owners = 0
            self._owners_seen = []
            self._inflight = []

    @property
    def stats(self) -> BackendStats:
        self._init_state()
        queue = getattr(self, 'queue', None)
        return BackendStats(qsize=queue.qsize() if queue is not None else 0,
                            written=self._written, batches=self._batches,
                            dropped_overflow=self._dropped_overflow, dropped_failed=self._dropped_failed,
                            conflicts=self._conflicts, retries=self._retries, last_error=self._last_error,
                            last_write_ts=self._last_write_ts, hand_off=bool(getattr(self, 'hand_off', False)))

    def start_writer(self, tg: asyncio.TaskGroup, name: str, owner=None):
        self._init_state()
        self._owners += 1
        if getattr(self, 'started', False):
            if owner is not None and any(seen is owner for seen in self._owners_seen):
                LOG.info('%s: one feed is using this backend instance for more than one channel', type(self).__name__)
            else:
                LOG.warning('%s: a second feed is sharing this backend instance', type(self).__name__)
            self._owners_seen.append(owner)
            return None
        self._owners_seen.append(owner)
        self.queue = asyncio.Queue(maxsize=self.max_depth)
        self._stopping = asyncio.Event()
        self.worker = tg.create_task(self.writer(), name=name)
        self.started = True
        return self.worker

    def begin_shutdown(self):
        stopping = getattr(self, '_stopping', None)
        if stopping is not None:
            stopping.set()

    async def stop(self):
        if not getattr(self, 'started', False):
            return False

        self._owners -= 1
        if self._owners_seen:
            self._owners_seen.pop()
        if self._owners > 0:
            return False

        self._stopping.set()
        try:
            self.queue.put_nowait(SHUTDOWN_SENTINEL)
            return True
        except asyncio.QueueFull:
            pass

        if self.overflow == 'block':
            with suppress(TimeoutError):
                await asyncio.wait_for(self.queue.put(SHUTDOWN_SENTINEL), self.SENTINEL_TIMEOUT)
                return True
            LOG.warning('%s: did not drain within %.1fs of shutdown', type(self).__name__, self.SENTINEL_TIMEOUT)

        self.queue.get_nowait()
        self._count_overflow_drop()
        self.queue.put_nowait(SHUTDOWN_SENTINEL)
        return True

    async def write(self, data):
        if not getattr(self, 'started', False):
            raise RuntimeError(f'{type(self).__name__}: no writer is running, so this backend cannot accept data')

        worker = getattr(self, 'worker', None)
        if worker is not None and worker.done():
            self._dropped_failed += 1
            if not self._orphaned:
                self._orphaned = True
                LOG.error('%s: the writer exited but data still being written. These messages are dropped, see stats.dropped_failed.', type(self).__name__)
            return

        if self.overflow == 'block':
            try:
                self.queue.put_nowait(data)
                return
            except asyncio.QueueFull:
                pass
            while not self._stopping.is_set():
                with suppress(TimeoutError):
                    await asyncio.wait_for(self.queue.put(data), self.BLOCK_POLL)
                    return
            self._count_overflow_drop()
            return

        while True:
            try:
                self.queue.put_nowait(data)
                return
            except asyncio.QueueFull:
                if self.overflow == 'drop_new':
                    self._count_overflow_drop()
                    return

                try:
                    oldest = self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue

                if oldest is SHUTDOWN_SENTINEL:
                    self.queue.put_nowait(SHUTDOWN_SENTINEL)
                    self._count_overflow_drop()
                    return
                self._count_overflow_drop()

    def _count_overflow_drop(self):
        if self._dropped_overflow == 0:
            LOG.warning('%s: queue full (max_depth=%d, overflow=%s) - dropping data', type(self).__name__, self.max_depth, self.overflow)
        self._dropped_overflow += 1

    async def writer(self):
        self.running = True
        try:
            while self.running:
                batch = await self._next_batch()
                if batch:
                    await self._write_with_retry(batch)
            await self.flush(self.flush_deadline)
        finally:
            self.running = False
            abandoned = len(self._inflight)
            self._inflight = []
            queue = getattr(self, 'queue', None)

            if queue is not None:
                while queue.qsize():
                    abandoned += queue.get_nowait() is not SHUTDOWN_SENTINEL
            if abandoned:
                self._dropped_failed += abandoned
                LOG.warning('%s: writer stopped with %d message(s) undelivered - counted as dropped',
                            type(self).__name__, abandoned)
            try:
                await self.close()
            except Exception as e:
                self._last_error = f'{type(e).__name__}: {e}'
                LOG.exception('%s: close() failed - data not yet flushed may be lost', type(self).__name__)

    async def _next_batch(self) -> list:
        first = await self.queue.get()
        if first is SHUTDOWN_SENTINEL:
            self.running = False
            return []

        batch = [first]
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.batch_interval

        while len(batch) < self.batch_max:
            try:
                item = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    item = await asyncio.wait_for(self.queue.get(), remaining)
                except TimeoutError:
                    break

            if item is SHUTDOWN_SENTINEL:
                self.running = False
                break
            batch.append(item)
        return batch

    async def _write_with_retry(self, batch: list):
        self._inflight = batch
        await self._deliver(batch, attempt=1)
        self._inflight = []

    async def _deliver(self, batch: list, attempt: int):
        while True:
            try:
                await self.connect()
                accepted = await self.write_batch(batch)
            except PermanentWriteError as e:
                self._last_error = f'{type(e.__cause__ or e).__name__}: {e}'
                self._dropped_failed += len(batch)
                LOG.error('%s: permanently rejected batch of %d (%s)',type(self).__name__, len(batch), self._last_error)
                return
            except self.retryable_exceptions as e:
                self._last_error = f'{type(e).__name__}: {e}'
                if not self._failing:
                    self._failing = True
                    LOG.log(self.FAILURE_LEVEL, '%s: write failed (%s), retrying', type(self).__name__, self._last_error)

                if attempt >= self.retry.max_attempts:
                    self._dropped_failed += len(batch)
                    self._failed_batches += 1
                    if self._failed_batches % 100 == 0:
                        LOG.error('%s: still failing - %d batches (%d messages) dropped. Error %s', type(self).__name__, self._failed_batches, self._dropped_failed, self._last_error)
                    return
                self._retries += 1
                await asyncio.sleep(self.retry.delay(attempt))
                attempt += 1
            else:
                if accepted is None:
                    self._written += len(batch)
                elif isinstance(accepted, tuple):
                    written, discarded = accepted
                    self._written += written
                    self._dropped_failed += discarded
                    self._conflicts += len(batch) - written - discarded
                else:
                    self._written += accepted
                    self._conflicts += len(batch) - accepted

                self._batches += 1
                self._last_write_ts = time.time()
                if self._failing:
                    self._failing = False
                    dropped_batches = self._failed_batches
                    self._failed_batches = 0
                    LOG.log(self.FAILURE_LEVEL, '%s: recovered after %d dropped batch(es)', type(self).__name__, dropped_batches)
                return

    async def flush(self, deadline: float):
        self._init_state()
        queue = getattr(self, 'queue', None)

        if queue is None:
            return
        pending = []

        while True:
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if item is SHUTDOWN_SENTINEL:
                self.running = False
                continue
            pending.append(item)

        if not pending:
            return

        try:
            async with asyncio.timeout(deadline):
                while pending:
                    batch = pending[:self.batch_max]
                    await self._write_with_retry(batch)
                    del pending[:len(batch)]
        except TimeoutError:
            self._inflight = []
            self._dropped_failed += len(pending)
            LOG.warning('%s: flush deadline (%.1fs) hit - %d messages dropped',
                        type(self).__name__, deadline, len(pending))

    async def connect(self):
        pass

    async def write_batch(self, batch: list):
        raise NotImplementedError

    async def close(self):
        pass

class BackendCallback:
    async def __call__(self, dtype, receipt_timestamp: float):
        data = dtype.to_dict(numeric_type=self.numeric_type, none_to=self.none_to)
        if not dtype.timestamp:
            data['timestamp'] = receipt_timestamp
        data['receipt_timestamp'] = receipt_timestamp
        await self.write(data)


class BackendBookCallback:
    async def _write_snapshot(self, book, receipt_timestamp: float):
        data = book.to_dict(numeric_type=self.numeric_type, none_to=self.none_to)
        del data['delta']
        if not book.timestamp:
            data['timestamp'] = receipt_timestamp
        data['receipt_timestamp'] = receipt_timestamp
        await self.write(data)

    async def __call__(self, book, receipt_timestamp: float):
        if self.snapshots_only:
            await self._write_snapshot(book, receipt_timestamp)
        else:
            data = book.to_dict(delta=book.delta is not None, numeric_type=self.numeric_type, none_to=self.none_to)
            if not book.timestamp:
                data['timestamp'] = receipt_timestamp
            data['receipt_timestamp'] = receipt_timestamp

            if book.delta is None:
                del data['delta']
            else:
                self.snapshot_count[book.symbol] += 1
            await self.write(data)
            if self.snapshot_interval <= self.snapshot_count[book.symbol] and book.delta:
                await self._write_snapshot(book, receipt_timestamp)
                self.snapshot_count[book.symbol] = 0
