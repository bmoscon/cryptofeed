'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from socket import error as socket_error
import time
from typing import Awaitable
import zlib

from websockets import ConnectionClosed
from websockets.exceptions import InvalidStatusCode

from cryptofeed.connection import AsyncConnection
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.defines import HUOBI, HUOBI_DM, HUOBI_SWAP, OKCOIN, OKEX


LOG = logging.getLogger('feedhandler')


class ConnectionHandler:
    def __init__(self, conn: AsyncConnection, subscribe: Awaitable, handler: Awaitable, retries: int, timeout=120, timeout_interval=30, exceptions=None, log_on_error=False):
        self.conn = conn
        self.subscribe = subscribe
        self.handler = handler
        self.retries = retries
        self.exceptions = exceptions
        self.log_on_error = log_on_error
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.running = True

    def start(self, loop: asyncio.AbstractEventLoop):
        loop.create_task(self._create_connection())

    async def _watcher(self):
        while self.conn.is_open and self.running:
            if self.conn.last_message:
                if time.time() - self.conn.last_message > self.timeout:
                    LOG.warning("%s: received no messages within timeout, restarting connection", self.conn.uuid)
                    await self.conn.close()
                    break
            await asyncio.sleep(self.timeout_interval)

    async def _create_connection(self):
        retries = 0
        rate_limited = 1
        delay = 1
        while (retries <= self.retries or self.retries == -1) and self.running:
            try:
                async with self.conn.connect() as connection:
                    # connection was successful, reset retry count and delay
                    retries = 0
                    rate_limited = 0
                    delay = 1
                    await self.subscribe(connection)
                    if self.timeout != -1:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self._watcher())
                    await self._handler(connection, self.handler)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error) as e:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", self.conn.uuid, str(e))
                            raise
                LOG.warning("%s: encountered connection issue %s - reconnecting in %.1f seconds...", self.conn.uuid, str(e), delay, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2
            except InvalidStatusCode as e:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", self.conn.uuid, str(e))
                            raise
                if e.status_code == 429:
                    LOG.warning("%s: Rate Limited - waiting %d seconds to reconnect", self.conn.uuid, rate_limited * 60)
                    await asyncio.sleep(rate_limited * 60)
                    rate_limited += 1
                else:
                    LOG.warning("%s: encountered connection issue %s - reconnecting in %.1f seconds...", self.conn.uuid, str(e), delay, exc_info=True)
                    await asyncio.sleep(delay)
                    retries += 1
                    delay *= 2
            except Exception as e:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", self.conn.uuid, str(e))
                            raise
                LOG.error("%s: encountered an exception, reconnecting in %.1f seconds", self.conn.uuid, delay, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        if not self.running:
            LOG.info('%s: terminate the connection handler because not running', self.conn.uuid)
        else:
            LOG.error('%s: failed to reconnect after %d retries - exiting', self.conn.uuid, retries)
            raise ExhaustedRetries()

    async def _handler(self, connection, handler):
        try:
            async for message in connection.read():
                if not self.running:
                    await connection.close()
                    return
                await handler(message, connection, self.conn.last_message)
        except Exception:
            if not self.running:
                return
            if self.log_on_error:
                if connection.uuid in {HUOBI, HUOBI_DM, HUOBI_SWAP}:
                    message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                elif connection.uuid in {OKCOIN, OKEX}:
                    message = zlib.decompress(message, -15)
                LOG.error("%s: error handling message %s", connection.uuid, message)
            # exception will be logged with traceback when connection handler
            # retries the connection
            raise
