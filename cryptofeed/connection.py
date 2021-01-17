'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterable, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple, Union

import aiohttp
import websockets


LOG = logging.getLogger('feedhandler')


def split_opt_addr(address: dict) -> List[dict]:
    return [{'opt': key, 'addr': val} for key, val in address.items()]


class AsyncConnection:
    conn_count: int = 0  # total number of AsyncConnection objects created

    def __init__(self, conn_id: str, ctx: dict):
        AsyncConnection.conn_count += 1
        self.id: str = conn_id  # unique identifier of the connection
        self.ctx: dict = ctx    # ctx (context) is passed to subscribe() and handle()
        self.received: int = 0  # count messages received since last watchdog check
        self.sent: int = 0      # count messages sent on the websocket
        self.socket: Union[websockets.WebSocketClientProtocol, aiohttp.ClientSession, None] = None

    @asynccontextmanager
    async def connect(self):
        await self._open()
        try:
            yield self
        finally:
            await self.close()

    async def _open(self):
        raise NotImplementedError

    @property
    def is_open(self) -> bool:
        # This is the Websocket implementation. Could be replaced by raise NotImplementedError.
        return self.socket and self.socket.open

    async def close(self):
        if self.is_open:
            # Swap socket value to avoid multiple closing occurring at the same time
            socket = self.socket
            self.socket = None
            await socket.close()
            LOG.info('%s: closed connection %r', self.id, socket.__class__.__name__)

    async def read(self) -> AsyncIterable[Tuple[bytes, float]]:
        # This is the Websocket implementation. Could be replaced by raise NotImplementedError.
        assert self.socket is not None
        async for data in self.socket:
            self.received += 1
            yield data, time.time()
            # if not self.is_open:
            #     LOG.info("%s: detect connection closed in read()", self.id)
            #     return


class HTTPAsyncConn(AsyncConnection):

    def __init__(self, address: Dict[str, str], feed_id: str, sleep: float,
                 feed_addr_compute: Optional[Callable[[], Iterable[dict]]]):
        """
        sleep: float
            time in seconds to limit rate of request polling.
        """
        if not isinstance(address, dict) or not all(addr[:4] == 'http' for addr in address.values()):
            raise ValueError(f'Invalid address for HTTPAsyncConn, must be a dict of quote/address, all starting with "http" but got: {address!r}')
        super().__init__(conn_id=f'{feed_id}-HTTP-{self.conn_count}', ctx={})
        self.opt_addr = split_opt_addr(address)
        self.sleep: float = sleep  # in seconds
        self.addr_compute: Optional[Callable[[], Iterable[dict]]] = feed_addr_compute

    @property
    def is_open(self) -> bool:
        return self.socket and not self.socket.closed

    async def _open(self):
        if self.is_open:
            LOG.exception('%s: HTTP session already created', self.id)
        else:
            LOG.info('%s: create HTTP session', self.id)
            self.socket = aiohttp.ClientSession()
        self.sent = -1  # no subscriptions on HTTP connection

    async def read(self) -> AsyncIterable[Tuple[bytes, float]]:
        while True:

            for ctx in self.addr_compute() if self.addr_compute else self.opt_addr:
                if not self.is_open:
                    LOG.info('%s: detect connection closed in read()', self.id)
                    return
                async with self.socket.get(ctx['addr']) as response:
                    timestamp = time.time()
                    response.raise_for_status()
                    data = await response.read()
                    self.received += 1
                    self.ctx = ctx
                    yield data, timestamp
                await asyncio.sleep(self.sleep)


class WSAsyncConn(AsyncConnection):

    def __init__(self, address: Dict[str, str], feed_id: str,
                 feed_msg_handler: Callable[[bytes, float, AsyncConnection], Awaitable], **kwargs):
        """
        kwargs:
            passed into the websocket connection.
        """
        if not isinstance(address, dict) or len(address) == 0 or list(address.values())[0][:2] != 'ws':
            raise ValueError(f'Invalid address for WSAsyncConn, must be a dict containing one single address starting with "ws" but got: {address!r}')
        ctx = split_opt_addr(address)[0]
        opt_or_count = ctx['opt'] if isinstance(ctx['opt'], str) and 0 < len(ctx['opt']) < 9 else self.conn_count
        super().__init__(conn_id=f'{feed_id}-WS-{opt_or_count}', ctx=ctx)
        self.handle: Callable[[bytes, float, AsyncConnection], Awaitable] = feed_msg_handler  # used by WSAsyncConn.send()
        self.ws_kwargs = kwargs  # optional args for websocket

    async def send(self, data: Union[str, bytes]):
        """Only used for Websocket, especially by Feed.subscribe()."""
        if not self.is_open:
            LOG.warning('%s: abort sending because websocket is closed - raise ConnectionError', self.id)
            raise ConnectionError

        await self.socket.send(data)
        self.sent += 1
        # slow down the subscription batch by waiting for a response or for a half of a second before next send
        try:
            data = await asyncio.wait_for(self.socket.recv(), timeout=0.5)
            await self.handle(data, time.time(), self)
        except asyncio.exceptions.TimeoutError:
            pass

    async def _open(self):
        if self.is_open:
            LOG.exception('%s: websocket already opened', self.id)
        else:
            LOG.info('%s: create websocket', self.id)
            self.socket = await websockets.connect(self.ctx['addr'], **self.ws_kwargs)
        self.sent = 0  # reset counter
