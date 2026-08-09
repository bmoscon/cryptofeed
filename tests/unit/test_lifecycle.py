'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import pytest

from cryptofeed import FeedHandler
from cryptofeed.backends.backend import BackendQueue
from cryptofeed.exceptions import ExhaustedRetries


CONFIG = {'log': {'disabled': True}, 'uvloop': False}


class StubFeed:
    """Duck-typed feed: runs until the stop event, optionally failing first."""
    def __init__(self, feed_id='STUB', fail_after=None):
        self.id = feed_id
        self.fail_after = fail_after
        self.ran = False
        self.finished = False

    async def run(self, stop_event):
        self.ran = True
        try:
            if self.fail_after is not None:
                await asyncio.sleep(self.fail_after)
                raise ExhaustedRetries()
            await stop_event.wait()
        finally:
            self.finished = True

    async def shutdown(self):
        pass


async def no_orphans():
    await asyncio.sleep(0)
    return {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}


async def test_start_stop_clean():
    fh = FeedHandler(config=CONFIG)
    feed = StubFeed()
    fh.add_feed(feed)

    async def stopper():
        while not fh.running:
            await asyncio.sleep(0.01)
        fh.request_stop()

    stop_task = asyncio.create_task(stopper())
    await fh.run_async(install_signal_handlers=False)
    await stop_task
    assert feed.ran and feed.finished
    assert not fh.running
    assert await no_orphans() == set()


async def test_feed_error_raises_and_stops_siblings():
    fh = FeedHandler(config=CONFIG)
    good = StubFeed('GOOD')
    bad = StubFeed('BAD', fail_after=0.01)
    fh.add_feed(good)
    fh.add_feed(bad)

    with pytest.raises(ExceptionGroup) as exc_info:
        await fh.run_async(install_signal_handlers=False)
    assert exc_info.group_contains(ExhaustedRetries)
    assert good.finished and bad.finished
    assert await no_orphans() == set()


async def test_feed_error_remove_feed_keeps_siblings():
    fh = FeedHandler(config=CONFIG, on_feed_error='remove_feed')
    good = StubFeed('GOOD')
    bad = StubFeed('BAD', fail_after=0.01)
    fh.add_feed(good)
    fh.add_feed(bad)

    async def stopper():
        while bad in fh.feeds:
            await asyncio.sleep(0.01)
        # the failed feed was removed, the good feed is still running
        assert good.ran and not good.finished
        fh.request_stop()

    stop_task = asyncio.create_task(stopper())
    await fh.run_async(install_signal_handlers=False)
    await stop_task
    assert good.finished
    assert bad not in fh.feeds and good in fh.feeds


async def test_add_feed_while_running():
    fh = FeedHandler(config=CONFIG)
    first = StubFeed('FIRST')
    late = StubFeed('LATE')
    fh.add_feed(first)

    async def orchestrate():
        while not fh.running:
            await asyncio.sleep(0.01)
        fh.add_feed(late)
        while not late.ran:
            await asyncio.sleep(0.01)
        fh.request_stop()

    task = asyncio.create_task(orchestrate())
    await fh.run_async(install_signal_handlers=False)
    await task
    assert first.finished and late.finished


async def test_invalid_on_feed_error():
    with pytest.raises(ValueError):
        FeedHandler(config=CONFIG, on_feed_error='explode')


def test_run_blocking_wrapper():
    fh = FeedHandler(config=CONFIG)

    class SelfStopper(StubFeed):
        async def run(self, stop_event):
            self.ran = True
            await asyncio.sleep(0.01)
            fh.request_stop()
            await stop_event.wait()
            self.finished = True

    feed = SelfStopper()
    fh.add_feed(feed)
    fh.run(install_signal_handlers=False)
    assert feed.ran and feed.finished


async def test_request_stop_idempotent_and_safe_before_run():
    fh = FeedHandler(config=CONFIG)
    fh.request_stop()  # no-op before run
    feed = StubFeed()
    fh.add_feed(feed)

    async def stopper():
        while not fh.running:
            await asyncio.sleep(0.01)
        fh.request_stop()
        fh.request_stop()

    task = asyncio.create_task(stopper())
    await fh.run_async(install_signal_handlers=False)
    await task
    assert feed.finished


class RecordingBackend(BackendQueue):
    """Interim-contract backend: drains the queue into a list."""
    def __init__(self, delay=0.0):
        self.written = []
        self.running = True
        self.delay = delay

    async def __call__(self, obj, receipt_timestamp):
        await self.write(obj)

    async def writer(self):
        while self.running:
            async with self.read_queue() as updates:
                if self.delay:
                    await asyncio.sleep(self.delay)
                self.written.extend(updates)


async def test_backend_flush_on_stop():
    backend = RecordingBackend()

    async with asyncio.TaskGroup() as tg:
        backend.start_writer(tg, name='test.backend')
        for i in range(50):
            await backend.write(i)
        await backend.stop()
    # everything before stop() called was flushed
    assert backend.written == list(range(50))


async def test_backend_writer_started_once():
    backend = RecordingBackend()
    async with asyncio.TaskGroup() as tg:
        first = backend.start_writer(tg, name='one')
        second = backend.start_writer(tg, name='two')
        assert first is not None and second is None
        await backend.stop()
