'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import time
import asyncio
from asyncio import Queue, CancelledError
from contextlib import asynccontextmanager, suppress
from typing import List, Union, AsyncIterable
from decimal import Decimal
import atexit
from aiohttp.client_reqrep import ClientResponse

import requests
import websockets
import aiohttp
from aiohttp.typedefs import StrOrURL
from yapic import json as json_parser

from cryptofeed.exceptions import ConnectionClosed


LOG = logging.getLogger('feedhandler')


class Connection:
    raw_data_callback = None

    async def read(self) -> bytes:
        raise NotImplementedError

    async def write(self, msg: str):
        raise NotImplementedError


class HTTPSync(Connection):
    def process_response(self, r, address, json=False, text=False, uuid=None):
        if self.raw_data_callback:
            self.raw_data_callback.sync_callback(r.text, time.time(), str(uuid), endpoint=address)
        r.raise_for_status()
        if json:
            return json_parser.loads(r.text, parse_float=Decimal)
        if text:
            return r.text
        return r

    def read(self, address: str, json=False, text=True, uuid=None):
        LOG.debug("HTTPSync: requesting data from %s", address)
        r = requests.get(address)
        return self.process_response(r, address, json=json, text=text, uuid=uuid)

    def write(self, address: str, data=None, json=False, text=True, uuid=None):
        LOG.debug("HTTPSync: post to %s", address)
        r = requests.post(address, data=data)
        return self.process_response(r, address, json=json, text=text, uuid=uuid)


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
        atexit.register(self.__del__)

    def __del__(self):
        # best effort clean up. Shutdown should be called on Feed/Exchange classes
        # and any user of the Async connection should use a context manager (via connect)
        # or call close manually. If not, we *might* be able to clean up the connection on exit
        try:
            if self.is_open:
                asyncio.ensure_future(self.close())
        except (RuntimeError, RuntimeWarning):
            # no event loop, ignore error
            pass

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
    def __init__(self, conn_id: str, proxy: StrOrURL = None):
        """
        conn_id: str
            id associated with the connection
        proxy: str, URL
            proxy url (GET only)
        """
        super().__init__(f'{conn_id}.http.{self.conn_count}')
        self.proxy = proxy

    @property
    def is_open(self) -> bool:
        return self.conn and not self.conn.closed

    def _handle_error(self, resp: ClientResponse, data: bytes):
        if resp.status != 200:
            LOG.error("%s: Status code %d for URL %s", self.id, resp.status, resp.url)
            LOG.error("%s: Headers: %s", self.id, resp.headers)
            LOG.error("%s: Resp: %s", self.id, data)
            resp.raise_for_status()

    async def _open(self):
        if self.is_open:
            LOG.warning('%s: HTTP session already created', self.id)
        else:
            LOG.debug('%s: create HTTP session', self.id)
            self.conn = aiohttp.ClientSession()
            self.sent = 0
            self.received = 0

    async def read(self, address: str, header=None, params=None, return_headers=False, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        LOG.debug("%s: requesting data from %s", self.id, address)
        while True:
            async with self.conn.get(address, headers=header, params=params, proxy=self.proxy) as response:
                data = await response.text()
                self.last_message = time.time()
                self.received += 1
                if self.raw_data_callback:
                    await self.raw_data_callback(data, self.last_message, self.id, endpoint=address, header=None if return_headers is False else dict(response.headers))
                if response.status == 429 and retry_count:
                    LOG.warning("%s: encountered a rate limit for address %s, retrying in 60 seconds", self.id, address)
                    retry_count -= 1
                    if retry_count < 0:
                        self._handle_error(response, data)
                    await asyncio.sleep(retry_delay)
                    continue
                self._handle_error(response, data)
                if return_headers:
                    return data, response.headers
                return data

    async def write(self, address: str, msg: str, header=None, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        while True:
            async with self.conn.post(address, data=msg, headers=header) as response:
                self.sent += 1
                data = await response.read()
                if self.raw_data_callback:
                    await self.raw_data_callback(data, time.time(), self.id, send=address)
                if response.status == 429 and retry_count:
                    LOG.warning("%s: encountered a rate limit for address %s, retrying in 60 seconds", self.id, address)
                    retry_count -= 1
                    if retry_count < 0:
                        self._handle_error(response, data)
                    await asyncio.sleep(retry_delay)
                    continue
                self._handle_error(response, data)
                return data

    async def delete(self, address: str, header=None, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        while True:
            async with self.conn.delete(address, headers=header) as response:
                self.sent += 1
                data = await response.read()
                if self.raw_data_callback:
                    await self.raw_data_callback(data, time.time(), self.id, send=address)
                if response.status == 429 and retry_count:
                    LOG.warning("%s: encountered a rate limit for address %s, retrying in 60 seconds", self.id, address)
                    retry_count -= 1
                    if retry_count < 0:
                        response.raise_for_status()
                    await asyncio.sleep(retry_delay)
                    continue
                response.raise_for_status()
                return data


class HTTPPoll(HTTPAsyncConn):
    def __init__(self, address: Union[List, str], conn_id: str, delay: float = 60, sleep: float = 1, proxy: StrOrURL = None):
        super().__init__(f'{conn_id}.http.{self.conn_count}', proxy)
        if isinstance(address, str):
            address = [address]
        self.address = address

        self.sleep = sleep
        self.delay = delay

    async def _read_address(self, address: str, header=None) -> str:
        LOG.debug("%s: polling %s", self.id, address)
        while True:
            if not self.is_open:
                LOG.error('%s: connection closed in read()', self.id)
                raise ConnectionClosed

            async with self.conn.get(address, headers=header, proxy=self.proxy) as response:
                data = await response.text()
                self.received += 1
                self.last_message = time.time()
                if self.raw_data_callback:
                    await self.raw_data_callback(data, self.last_message, self.id, endpoint=address)
                if response.status != 429:
                    response.raise_for_status()
                    return data
            LOG.warning("%s: encountered a rate limit for address %s, retrying in %f seconds", self.id, address, self.delay)
            await asyncio.sleep(self.delay)

    async def read(self, header=None) -> AsyncIterable[str]:
        while True:
            for addr in self.address:
                yield await self._read_address(addr, header)
            await asyncio.sleep(self.sleep)


class HTTPConcurrentPoll(HTTPPoll):
    """Polls each address concurrently in it's own Task"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queue = Queue()

    async def _poll_address(self, address: str, header=None):
        while True:
            data = await self._read_address(address, header)
            await self._queue.put(data)
            await asyncio.sleep(self.sleep)

    async def read(self, header=None) -> AsyncIterable[str]:
        tasks = asyncio.gather(*(self._poll_address(address, header) for address in self.address))

        try:
            while not tasks.done():
                with suppress(asyncio.exceptions.TimeoutError):
                    yield await asyncio.wait_for(self._queue.get(), timeout=1)
        finally:
            if not tasks.done():
                tasks.cancel()
                with suppress(CancelledError):
                    await tasks
            elif tasks.exception() is not None:
                raise tasks.exception()


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
            if self.raw_data_callback:
                await self.raw_data_callback(None, time.time(), self.id, connect=self.address)
            self.conn = await websockets.connect(self.address, **self.ws_kwargs)
        self.sent = 0
        self.received = 0
        self.last_message = None

    async def read(self) -> AsyncIterable:
        if not self.is_open:
            LOG.error('%s: connection closed in read()', id(self))
            raise ConnectionClosed
        if self.raw_data_callback:
            async for data in self.conn:
                self.received += 1
                self.last_message = time.time()
                await self.raw_data_callback(data, self.last_message, self.id)
                yield data
        else:
            async for data in self.conn:
                self.received += 1
                self.last_message = time.time()
                yield data

    async def write(self, data: str):
        if not self.is_open:
            raise ConnectionClosed

        if self.raw_data_callback:
            await self.raw_data_callback(data, time.time(), self.id, send=self.address)
        await self.conn.send(data)
        self.sent += 1
