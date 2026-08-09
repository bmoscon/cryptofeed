'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import time
from contextlib import asynccontextmanager

import pytest

from cryptofeed.connection_handler import ConnectionHandler
from cryptofeed.exceptions import ExhaustedRetries


class FakeConn:
    """Connection double: serves queued messages, then blocks until closed."""
    def __init__(self, messages=None, fail_connects=0):
        self.id = 'fake.ws.0'
        self.uuid = self.id
        self.messages = list(messages or [])
        self.fail_connects = fail_connects
        self.connect_count = 0
        self.last_message = None
        self._closed = asyncio.Event()
        self._open = False

    @property
    def is_open(self):
        return self._open

    @asynccontextmanager
    async def connect(self):
        self.connect_count += 1
        if self.fail_connects >= self.connect_count:
            raise ConnectionResetError('connect refused')
        self._open = True
        self._closed = asyncio.Event()
        try:
            yield self
        finally:
            self._open = False

    async def close(self):
        self._open = False
        self._closed.set()

    async def read(self):
        for msg in self.messages:
            self.last_message = time.time()
            yield msg
        await self._closed.wait()
        raise ConnectionResetError('closed')


def make_handler(conn, retries=2, timeout=-1, **kwargs):
    received = []

    async def subscribe(connection):
        pass

    async def handler(msg, connection, ts):
        received.append(msg)

    async def authenticate(connection):
        pass

    ch = ConnectionHandler(conn, subscribe, handler, authenticate, retries, timeout=timeout, **kwargs)
    return ch, received


async def test_messages_flow_and_graceful_stop():
    conn = FakeConn(messages=['a', 'b', 'c'])
    ch, received = make_handler(conn)

    async def stopper():
        while len(received) < 3:
            await asyncio.sleep(0.01)
        await ch.request_stop()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(ch.run())
        tg.create_task(stopper())
    assert received == ['a', 'b', 'c']


async def test_retry_budget_exhausts(monkeypatch):
    sleeps = []
    orig_sleep = asyncio.sleep

    async def fast_sleep(t):
        sleeps.append(t)
        await orig_sleep(0)

    monkeypatch.setattr('cryptofeed.connection_handler.asyncio.sleep', fast_sleep)
    conn = FakeConn(fail_connects=100)
    ch, _ = make_handler(conn, retries=3)
    with pytest.raises(ExhaustedRetries):
        await ch.run()
    # start_delay sleep + exponential backoff: 1, 2, 4, 8
    assert sleeps[1:] == [1, 2, 4, 8]


async def test_backoff_resets_after_successful_connect(monkeypatch):
    sleeps = []
    orig_sleep = asyncio.sleep

    async def fast_sleep(t):
        sleeps.append(t)
        await orig_sleep(0)

    monkeypatch.setattr('cryptofeed.connection_handler.asyncio.sleep', fast_sleep)

    class FlakyConn(FakeConn):
        async def read(self):
            self.last_message = time.time()
            yield 'msg'
            raise ConnectionResetError('dropped')

    conn = FlakyConn(fail_connects=2)
    ch, received = make_handler(conn, retries=2)

    async def stopper():
        while conn.connect_count < 4:
            await orig_sleep(0)
        await ch.request_stop()

    stop = asyncio.create_task(stopper())
    await ch.run()
    stop.cancel()
    # two failed connects (backoff 1, 2), then success resets delay to 1
    assert sleeps[1:3] == [1, 2]
    assert 1 in sleeps[3:]


async def test_watchdog_restarts_stale_connection(monkeypatch):
    orig_sleep = asyncio.sleep

    async def quick(t):
        await orig_sleep(0.01)

    monkeypatch.setattr('cryptofeed.connection_handler.asyncio.sleep', quick)

    class StaleConn(FakeConn):
        async def read(self):
            self.last_message = time.time() - 10_000
            if False:
                yield
            await self._closed.wait()
            raise ConnectionResetError('watchdog closed')

    conn = StaleConn()
    ch, _ = make_handler(conn, retries=1, timeout=60, timeout_interval=1)

    async def stopper():
        while conn.connect_count < 2:
            await orig_sleep(0.01)
        await ch.request_stop()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(ch.run())
        tg.create_task(stopper())
    # the watchdog closed the stale connection, forcing at least one reconnect
    assert conn.connect_count >= 2


async def test_no_watchdog_leak_after_run():
    conn = FakeConn(messages=['x'])
    ch, received = make_handler(conn, timeout=120)

    async def stopper():
        while not received:
            await asyncio.sleep(0.01)
        await ch.request_stop()

    async with asyncio.TaskGroup() as tg:
        tg.create_task(ch.run())
        tg.create_task(stopper())
    await asyncio.sleep(0)
    leftover = {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}
    assert not any('watchdog' in (t.get_name() or '') for t in leftover)
