'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
import zlib
from contextlib import suppress

from websockets import ConnectionClosed as WebsocketClosed

from cryptofeed.backends.backend import RetryPolicy
from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import HTX, HTX_SWAP, OKX
from cryptofeed.exceptions import ConnectionClosed, ExhaustedRetries


LOG = logging.getLogger(__name__)

# the far end going away, as the transport reports it: logged at WARNING; anything else is an error worth a traceback
TRANSIENT = (WebsocketClosed, ConnectionClosed, OSError)


class ConnectionHandler:
    STABILITY_WINDOW = 60.0
    BACKOFF = RetryPolicy(base=1.0, max_delay=120.0)

    def __init__(self, conn: AsyncConnection, subscribe, handler, retries: int, timeout=120, timeout_interval=30, exceptions=None, log_on_error=False, start_delay=0, keepalive=None, keepalive_interval: float = None):
        self.conn = conn
        self.subscribe = subscribe
        self.handler = handler
        self.retries = retries
        self.exceptions = tuple(exceptions) if exceptions else ()
        self.log_on_error = log_on_error
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.keepalive = keepalive
        self.keepalive_interval = keepalive_interval
        self.running = True
        self.start_delay = start_delay
        self._stop = asyncio.Event()
        self._tripped = False

    async def request_stop(self):
        self.running = False
        self._stop.set()
        with suppress(Exception):
            await self.conn.close()

    async def _wait(self, seconds: float) -> bool:
        if seconds > 0:
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), seconds)
        return not self.running

    async def _keepalive(self):
        while self.conn.is_open and self.running:
            await asyncio.sleep(self.keepalive_interval)

            if not (self.conn.is_open and self.running):
                return

            try:
                await self.keepalive(self.conn)
            except TRANSIENT:
                return
            except Exception:
                LOG.error('%s: keepalive failed - restarting the connection', self.conn.uuid, exc_info=True)
                await self.conn.close()
                return

    async def _watcher(self):
        seen = self.conn.received
        quiet_since = time.monotonic()

        while self.conn.is_open and self.running:
            await asyncio.sleep(self.timeout_interval)

            if self.conn.received != seen:
                seen, quiet_since = self.conn.received, time.monotonic()
            elif time.monotonic() - quiet_since > self.timeout:
                if seen:
                    LOG.warning('%s: received no messages within %gs, restarting connection', self.conn.uuid, self.timeout)
                else:
                    LOG.warning('%s: no message received within %gs of subscribing, restarting connection', self.conn.uuid, self.timeout)

                self._tripped = True
                self.conn.record_watchdog_trip()
                await self.conn.close()

                return

    async def run(self):
        try:
            if await self._wait(self.start_delay):
                return

            attempt = 0
            while self.running:
                failure, healthy = await self._session()
                if not self.running:
                    break
                if healthy:
                    attempt = 0
                    if failure is None:
                        continue

                attempt += 1
                if self.retries != -1 and attempt > self.retries:
                    LOG.error('%s: failed to reconnect after %d retries - exiting', self.conn.uuid, self.retries)
                    raise ExhaustedRetries()

                delay = self.BACKOFF.delay(attempt)
                budget = '' if self.retries == -1 else f' of {self.retries}'

                if failure is None:
                    LOG.warning('%s: connection closed by the venue shortly after subscribing - reconnecting in %.1f seconds (attempt %d%s)', self.conn.uuid, delay, attempt, budget)
                elif isinstance(failure, TRANSIENT):
                    LOG.warning('%s: encountered connection issue %s - reconnecting in %.1f seconds (attempt %d%s)', self.conn.uuid, failure, delay, attempt, budget)
                else:
                    LOG.error('%s: encountered an exception, reconnecting in %.1f seconds (attempt %d%s)', self.conn.uuid, delay, attempt, budget, exc_info=failure)

                if await self._wait(delay):
                    break
            LOG.info('%s: terminate the connection handler because not running', self.conn.uuid)

        finally:
            with suppress(Exception):
                await self.conn.close()

    async def _session(self):
        self._tripped = False
        subscribed_at = None
        failure = None

        try:
            async with self.conn.connect() as connection:
                if not self.running:
                    return None, True

                await self.subscribe(connection)
                subscribed_at = time.monotonic()
                tasks = []

                if self.timeout != -1:
                    tasks.append(asyncio.create_task(self._watcher(), name=f'{self.conn.id}.watchdog'))

                if self.keepalive is not None and self.keepalive_interval:
                    tasks.append(asyncio.create_task(self._keepalive(), name=f'{self.conn.id}.keepalive'))

                try:
                    await self._handler(connection, self.handler)
                finally:
                    for task in tasks:
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
        except self.exceptions as e:
            LOG.warning('%s: encountered exception %s which is on the ignore list. Raising', self.conn.uuid, e)
            raise
        except Exception as e:
            failure = e

        long_lived = subscribed_at is not None and time.monotonic() - subscribed_at >= self.STABILITY_WINDOW
        return failure, long_lived or self._tripped or not self.conn.paced

    async def _handler(self, connection, handler):
        message = None
        try:
            async for message in connection.read():
                await handler(message, connection, self.conn.last_message)
                message = None

                if not self.running:
                    await connection.close()
                    return
        except Exception:
            if not self.running:
                return

            if self.log_on_error and message is not None:
                if isinstance(message, bytes):
                    with suppress(Exception):
                        if connection.uuid.startswith((f'{HTX}.', f'{HTX_SWAP}.')):
                            message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                        elif connection.uuid.startswith(f'{OKX}.'):
                            message = zlib.decompress(message, -15)
                LOG.error('%s: error handling message %s', connection.uuid, message)
            raise
