"""Copyright (C) 2020-2021  Cryptofeed contributors.

Please see the LICENSE file for the terms and conditions
associated with this software.
"""
import asyncio
import logging
import zlib
from json import JSONDecodeError
from typing import Callable, Optional

import yapic.json._json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import HUOBI, HUOBI_DM, OKCOIN, OKEX
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.feed import Feed


LOG = logging.getLogger('feedhandler')


class Runner:

    def __init__(self, feed: Feed, conn: AsyncConnection, timeout: float, max_retries: int):
        self.feed: Feed = feed
        self.conn: AsyncConnection = conn
        self.timeout: float = timeout  # in seconds
        self.max_retries: int = max_retries

    @property
    def id(self):
        return self.conn.id

    async def shutdown(self):
        LOG.info('%s: shutdown runner max_retries: %r -> 0 (zero flags shutdown)', self.id, self.max_retries)
        self.max_retries = 0  # Stop infinite loop
        await self.conn.close()

    async def run(self, do_handle: bool, capture_cb: Callable, log_msg: bool):
        """Connect to exchange, subscribe and handle responses."""
        LOG.info('%s: Start infinite loop handle=%s capture=%s log_msg=%s max_retries=%s',
                 self.id, do_handle, not not capture_cb, log_msg, self.max_retries)
        # To shutdown the loop: set max_retries=0 and close the socket
        retries = delay = 1
        while self.max_retries:
            try:
                async with self.conn.connect() as conn:
                    keep = await self.feed.subscribe(conn)
                    if conn.sent == 0 and not keep:
                        LOG.warning('%s: nothing subscribed - close the connection', self.id)
                        return
                    if conn.sent > 0:
                        LOG.info('%s: sent %s messages during subscription', self.id, conn.sent)

                    task = asyncio.create_task(self._watch())
                    task.set_name(f'watch_{self.id}')
                    # TODO: Replace _watch() by argument timeout: ClientSession.get(timeout=120) & similar for WS
                    #  /!\  Multiple _watch() of the same Runner may be running in parallel on successive disconnections

                    await self._handle(do_handle, capture_cb, log_msg)

                    # connection was successful, reset retry count and delay
                    retries = delay = 1

            except Exception as e:
                if 0 < self.max_retries < retries:
                    LOG.critical('%s: failed to reconnect after %d retries - exiting', self.id, retries)
                    raise ExhaustedRetries() from e

                if self.max_retries:
                    LOG.exception('%s: encountered %r, reconnect in %.1f seconds', self.id, e, delay)
                    await asyncio.sleep(delay)
                    retries += 1
                    delay *= 2

                if self.max_retries == 0:
                    LOG.warning('%s: encountered %r, but max_retries=0 - shutdown AsyncConnection.run()', self.id, e)
                    return

    async def _handle(self, do_handle: bool, capture_cb: Optional[Callable], log_msg: bool):
        data = None
        try:
            if capture_cb and do_handle:
                async for data, timestamp in self.conn.read():
                    await capture_cb(data, timestamp, self.feed.id)  # TODO replace capture by callbacks
                    try:
                        await self.feed.handle(data, timestamp, self.conn)
                    except JSONDecodeError or yapic.json.JsonDecodeError as why:
                        LOG.warning('%s: %r - skip invalid JSON: %.500r', self.id, why, self.decompress(data))
            elif capture_cb:
                async for data, timestamp in self.conn.read():
                    await capture_cb(data, timestamp, self.feed.id)
            else:
                async for data, timestamp in self.conn.read():
                    try:
                        await self.feed.handle(data, timestamp, self.conn)
                    except JSONDecodeError or yapic.json.JsonDecodeError as why:
                        LOG.warning('%s: %r - skip invalid JSON: %.500r', self.id, why, self.decompress(data))
        except Exception as why:
            LOG.error('%s: encountered %r - end of AsyncConnection._handle()', self.id, why)
            if data is not None and log_msg:
                LOG.error('%s: error handling %r', self.id, self.decompress(data))
            # exception will be logged with traceback when connection handler
            # retries the connection
            raise

    def decompress(self, data: bytes) -> bytes:
        if self.feed.id in (HUOBI, HUOBI_DM):
            return zlib.decompress(data, 16 + zlib.MAX_WBITS)
        if self.feed.id in (OKCOIN, OKEX):
            return zlib.decompress(data, -15)
        return data

    async def _watch(self):  # TODO: replace _watch() by timeout in ClientSession.get(timeout=120)
        if self.timeout == 0:
            LOG.info('%s: timeout=0, disable connection timeout watching', self.id)
            return

        timeout = last_log_timeout = high = low = self.timeout
        self.conn.received = -1
        LOG.info('%s: initial timeout: %d seconds (%.2f minutes)', self.id, self.timeout, self.timeout / 60)

        while self.conn.is_open:
            if self.conn.received == 0:
                self.timeout = 30 + 2 * timeout  # Increase for next watch
                LOG.warning('%s: reset connection, no msg within %d seconds (%.2f minutes) next timeout: %d s (%.2f m)',
                            self.id, timeout, timeout / 60, self.timeout, self.timeout / 60)
                try:
                    await self.conn.close()
                except Exception as why:
                    LOG.warning('%s: cannot close because %r', self.id, why)
                return

            # Compute timeout to be between 20 messages (low frequency) and 1000 messages (high frequency)
            if self.conn.received > 0:
                freq = self.conn.received / timeout
                target = 20 / freq + 20  # +20 seconds = security margin
                if timeout > target:
                    timeout = (target + 8 * timeout + high) / 10  # Average in favor of the greatest values
                    low = min(timeout, low)
                else:
                    timeout = (timeout + 9 * target) / 10
                    high = max(timeout, high)
                if abs(last_log_timeout / timeout - 1) > 0.2:  # Only log when change is greater than 20%
                    LOG.info('%s: adaptive timeout: %d -> %d seconds (%.2f msg/sec -> target %d s) min-max: %d-%d',
                             self.id, last_log_timeout, timeout, freq, target, low, high)
                    last_log_timeout = timeout

            self.conn.received = 0  # Reset counter just before sleep
            await asyncio.sleep(timeout)

        freq = self.conn.received / timeout
        self.timeout = 30 + timeout  # Increase for next watch
        LOG.info('%s: connection closed - stop watching - %.2f msg/sec timeout: %d -> %d seconds min-max: %d-%d',
                 self.id, freq, timeout, self.timeout, low, high)
