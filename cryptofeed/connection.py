'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from contextlib import asynccontextmanager
import time
from typing import List, Union, AsyncIterable

import aiohttp
import websockets
import requests

from cryptofeed.exceptions import ConnectionClosed


LOG = logging.getLogger('feedhandler')


class Connection:
    async def read(self) -> bytes:
        raise NotImplementedError

    async def write(self, msg: str):
        raise NotImplementedError


class HTTPSync(Connection):
    def read(self, address: str, json=False, text=True):
        LOG.debug("HTTPSync: requesting data from %s", address)
        r = requests.get(address)
        r.raise_for_status()
        if json:
            return r.json()
        if text:
            return r.text
        return r


class AsyncConnection(Connection):
    conn_count: int = 0

    def __init__(self, conn_id: str):
        """
        conn_id: str
            the unique identifier for the connection
        """
        AsyncConnection.conn_count += 1
        self.id: str = conn_id
        self.received: int = 0
        self.sent: int = 0
        self.last_message = None
        self.conn: Union[websockets.WebSocketClientProtocol, aiohttp.ClientSession] = None

    @property
    def uuid(self):
        return self.id

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
        raise NotImplementedError

    async def close(self):
        if self.is_open:
            conn = self.conn
            self.conn = None
            await conn.close()
            LOG.info('%s: closed connection %r', self.id, conn.__class__.__name__)


class HTTPAsyncConn(AsyncConnection):
    def __init__(self, conn_id: str):
        """
        conn_id: str
            id associated with the connection
        sleep: float
            time in seconds to limit rate of request polling.
        """
        super().__init__(f'{conn_id}.http.{self.conn_count}')

    @property
    def is_open(self) -> bool:
        return self.conn and not self.conn.closed

    async def _open(self):
        if self.is_open:
            LOG.warning('%s: HTTP session already created', self.id)
        else:
            LOG.debug('%s: create HTTP session', self.id)
            self.conn = aiohttp.ClientSession()
            self.sent = 0
            self.received = 0

    async def read(self, address: str) -> bytes:
        if not self.is_open:
            await self._open()

        LOG.debug("%s: requesting data from %s", self.id, address)
        async with self.conn.get(address) as response:
            response.raise_for_status()
            data = await response.text()
            self.received += 1
            self.last_message = time.time()
            return data

    async def write(self, address: str, msg: str, header=None):
        if not self.is_open:
            await self._open()

        async with self.conn.post(address, data=msg, headers=header) as response:
            response.raise_for_status()
            data = await response.read()
            self.sent += 1
            return data


class HTTPPoll(HTTPAsyncConn):
    def __init__(self, address: Union[List, str], conn_id: str, delay: float = 60, sleep: float = 1):
        super().__init__(f'{conn_id}.http.{self.conn_count}')
        if isinstance(address, str):
            address = [address]
        self.address = address

        self.sleep = sleep
        self.delay = delay

    async def read(self) -> AsyncIterable:
        while True:
            for addr in self.address:
                if not self.is_open:
                    LOG.error('%s: connection closed in read()', self.id)
                    raise ConnectionClosed
                LOG.debug("%s: polling %s", self.id, addr)
                async with self.conn.get(addr) as response:
                    response.raise_for_status()
                    data = await response.text()
                    self.received += 1
                    self.last_message = time.time()
                    yield data
                    await asyncio.sleep(self.sleep)
            await asyncio.sleep(self.delay)


class WSAsyncConn(AsyncConnection):

    def __init__(self, address: str, conn_id: str, **kwargs):
        """
        address: str
            the websocket address to connect to
        conn_id: str
            the identifier of this connection
        kwargs:
            passed into the websocket connection.
        """
        if not address.startswith("wss://"):
            raise ValueError(f'Invalid address, must be a wss address. Provided address is: {address!r}')
        self.address = address
        super().__init__(f'{conn_id}.ws.{self.conn_count}')
        self.ws_kwargs = kwargs

    @property
    def is_open(self) -> bool:
        return self.conn and not self.conn.closed

    async def _open(self):
        if self.is_open:
            LOG.warning('%s: websocket already open', self.id)
        else:
            LOG.debug('%s: connecting to %s', self.id, self.address)
            self.conn = await websockets.connect(self.address, **self.ws_kwargs)
        self.sent = 0
        self.received = 0

    async def read(self) -> AsyncIterable:
        if not self.is_open:
            LOG.error('%s: connection closed in read()', self.id)
            raise ConnectionClosed
        async for data in self.conn:
            self.received += 1
            self.last_message = time.time()
            yield data

    async def write(self, data: str):
        if not self.is_open:
            LOG.error('%s: connection closed in write()', self.id)
            raise ConnectionClosed

        await self.conn.send(data)
        self.sent += 1
