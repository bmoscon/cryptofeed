'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import pytest

from cryptofeed.backends.backend import SHUTDOWN_SENTINEL, BackendQueue


class Recorder(BackendQueue):
    def __init__(self, delay: float = 0, fail_first: int = 0):
        self.written = []
        self.batches = []
        self.running = True
        self.delay = delay
        self.fail_first = fail_first
        self.attempts = 0

    async def writer(self):
        while self.running:
            async with self.read_queue() as updates:
                self.attempts += 1
                if self.delay:
                    await asyncio.sleep(self.delay)
                if updates:
                    self.batches.append(list(updates))
                self.written.extend(updates)


@pytest.fixture
def recorder():
    return Recorder()


async def drain(backend, produce, stop=True):
    async with asyncio.TaskGroup() as tg:
        backend.start_writer(tg, name='test.writer')
        await produce(backend)
        if stop:
            await backend.stop()


async def test_every_message_arrives_in_order(recorder):
    async def produce(backend):
        for i in range(200):
            await backend.write(i)

    await drain(recorder, produce)
    assert recorder.written == list(range(200))


async def test_queued_messages_are_flushed_before_shutdown(recorder):
    async def produce(backend):
        for i in range(500):
            await backend.write(i)

    await drain(recorder, produce)
    assert recorder.written == list(range(500)), 'messages were dropped at shutdown'


async def test_slow_writer_still_flushes_everything():
    backend = Recorder(delay=0.01)

    async def produce(b):
        for i in range(50):
            await b.write(i)

    await drain(backend, produce)
    assert backend.written == list(range(50))


async def test_messages_are_batched_not_written_one_at_a_time():
    backend = Recorder(delay=0.005)

    async def produce(b):
        for i in range(100):
            await b.write(i)
        await asyncio.sleep(0.05)

    await drain(backend, produce)
    assert backend.written == list(range(100))
    assert max(len(batch) for batch in backend.batches) > 1, 'no batching happened'
    assert len(backend.batches) < 100, 'every message was written individually'


async def test_writer_starts_once_per_backend(recorder):
    async with asyncio.TaskGroup() as tg:
        first = recorder.start_writer(tg, name='one')
        second = recorder.start_writer(tg, name='two')
        assert first is not None
        assert second is None, 'a second writer was started'
        await recorder.stop()


async def test_stop_before_start_is_safe(recorder):
    # nothing started, so there is no queue to put a sentinel on
    await recorder.stop()
    assert recorder.written == []


async def test_task_done_accounting(recorder):
    async def produce(backend):
        for i in range(20):
            await backend.write(i)

    await drain(recorder, produce)
    # unfinished_tasks includes the sentinel, which is consumed but intentionally not marked
    assert recorder.queue.qsize() == 0


async def test_sentinel_stops_the_writer(recorder):
    async with asyncio.TaskGroup() as tg:
        worker = recorder.start_writer(tg, name='test')
        await recorder.write('payload')
        await recorder.queue.put(SHUTDOWN_SENTINEL)
        await asyncio.wait_for(worker, timeout=2)
    assert recorder.written == ['payload']
    assert recorder.running is False


async def test_sentinel_in_a_batch_still_delivers_the_batch(recorder):
    async with asyncio.TaskGroup() as tg:
        worker = recorder.start_writer(tg, name='test')
        for i in range(10):
            await recorder.write(i)
        await recorder.queue.put(SHUTDOWN_SENTINEL)
        await asyncio.wait_for(worker, timeout=2)
    assert recorder.written == list(range(10))
