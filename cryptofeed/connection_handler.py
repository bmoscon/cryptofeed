'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from contextlib import suppress
from socket import error as socket_error
import time
from typing import Awaitable
import zlib

from websockets import ConnectionClosed

from cryptofeed.connection import AsyncConnection
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.defines import HTX, HTX_SWAP, OKX


LOG = logging.getLogger(__name__)


class ConnectionHandler:
    def __init__(self, conn: AsyncConnection, subscribe: Awaitable, handler: Awaitable, retries: int, timeout=120, timeout_interval=30, exceptions=None, log_on_error=False, start_delay=0, keepalive: Awaitable = None, keepalive_interval: float = None):
        self.conn = conn
        self.subscribe = subscribe
        self.handler = handler
        self.retries = retries
        self.exceptions = exceptions
        self.log_on_error = log_on_error
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.keepalive = keepalive
        self.keepalive_interval = keepalive_interval
        self.running = True
        self.start_delay = start_delay

    async def request_stop(self):
        # prevent reconnection and close the connection
        self.running = False
        with suppress(Exception):
            await self.conn.close()

    def _record_watchdog_trip(self):
        record = getattr(self.conn, 'record_watchdog_trip', None)
        if record is not None:
            record()

    async def _keepalive(self):
        while self.conn.is_open and self.running:
            await asyncio.sleep(self.keepalive_interval)

            if not (self.conn.is_open and self.running):
                return

            try:
                await self.keepalive(self.conn)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error):
                return
            except Exception:
                LOG.exception('%s: keepalive failed', self.conn.uuid)
                return

    async def _watcher(self):
        while self.conn.is_open and self.running:
            if self.conn.last_message:
                if time.time() - self.conn.last_message > self.timeout:
                    LOG.warning("%s: received no messages within timeout, restarting connection", self.conn.uuid)
                    self._record_watchdog_trip()
                    await self.conn.close()
                    break
            await asyncio.sleep(self.timeout_interval)

    async def run(self):
        try:
            await asyncio.sleep(self.start_delay)
            retries = 0
            delay = 1

            while (retries <= self.retries or self.retries == -1) and self.running:
                watchdog = pinger = None

                try:
                    async with self.conn.connect() as connection:
                        await self.subscribe(connection)
                        # connection was successful, reset retry count and delay
                        retries = 0
                        delay = 1
                        try:
                            if self.timeout != -1:
                                watchdog = asyncio.get_running_loop().create_task(self._watcher(), name=f'{self.conn.id}.watchdog')
                            if self.keepalive is not None and self.keepalive_interval:
                                pinger = asyncio.get_running_loop().create_task(self._keepalive(), name=f'{self.conn.id}.keepalive')
                            await self._handler(connection, self.handler)
                        finally:
                            for task in (watchdog, pinger):
                                if task is not None:
                                    task.cancel()
                                    with suppress(asyncio.CancelledError):
                                        await task
                except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error) as e:
                    if self.exceptions:
                        for ex in self.exceptions:
                            if isinstance(e, ex):
                                LOG.warning("%s: encountered exception %s which is on the ignore list. Raising", self.conn.uuid, str(e))
                                raise
                    if not self.running:
                        break
                    LOG.warning("%s: encountered connection issue %s - reconnecting in %.1f seconds", self.conn.uuid, str(e), delay, exc_info=True)
                    await asyncio.sleep(delay)
                    retries += 1
                    delay *= 2
                except Exception as e:
                    if self.exceptions:
                        for ex in self.exceptions:
                            if isinstance(e, ex):
                                LOG.warning("%s: encountered exception %s which is on the ignore list. Raising", self.conn.uuid, str(e))
                                raise
                    if not self.running:
                        break
                    LOG.error("%s: encountered an exception, reconnecting in %.1f seconds", self.conn.uuid, delay, exc_info=True)
                    await asyncio.sleep(delay)
                    retries += 1
                    delay *= 2

            if self.running:
                LOG.error('%s: failed to reconnect after %d retries - exiting', self.conn.uuid, retries)
                raise ExhaustedRetries()
            LOG.info('%s: terminate the connection handler because not running', self.conn.uuid)
        finally:
            with suppress(Exception):
                await self.conn.close()

    async def _handler(self, connection, handler):
        try:
            async for message in connection.read():
                await handler(message, connection, self.conn.last_message)
                if not self.running:
                    await connection.close()
                    return
        except Exception:
            if not self.running:
                return
            if self.log_on_error:
                if connection.uuid in {HTX, HTX_SWAP}:
                    message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                elif connection.uuid in {OKX}:
                    message = zlib.decompress(message, -15)
                LOG.error("%s: error handling message %s", connection.uuid, message)
            # exception will be logged with traceback when connection handler
            # retries the connection
            raise
