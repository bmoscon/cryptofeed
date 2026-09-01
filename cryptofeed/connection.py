'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import time
import asyncio
import weakref
from contextlib import asynccontextmanager
from typing import List, Optional, Union, AsyncIterable
from dataclasses import dataclass

from aiohttp.client_reqrep import ClientResponse
from websockets.asyncio.client import connect, ClientConnection
from websockets.protocol import State
import aiohttp
from aiohttp.typedefs import StrOrURL

from cryptofeed.exceptions import ConnectionClosed
from cryptofeed.symbols import str_to_symbol


LOG = logging.getLogger(__name__)
_LIVE = weakref.WeakSet()


@dataclass(frozen=True)
class ConnectionStats:
    id: str
    created: float
    connects: int
    reconnects: int
    watchdog_trips: int
    received: int
    sent: int
    last_message: Optional[float]
    open: bool


def connection_stats(exchange: str = None, since: float = None) -> dict:
    out = {}
    for conn in list(_LIVE):
        if since is not None and conn.created < since:
            continue
        # prefix match, exchange ids can contain periods
        if exchange is not None and not conn.id.startswith(f'{exchange}.'):
            continue
        out[conn.id] = conn.stats
    return dict(sorted(out.items()))


class Connection:
    raw_data_callback = None

    async def read(self) -> bytes:
        raise NotImplementedError

    async def write(self, msg: str):
        raise NotImplementedError


class AsyncConnection(Connection):
    conn_count: int = 0

    def __init__(self, conn_id: str, subscription=None):
        """
        conn_id: str
            the unique identifier for the connection
        subscription: dict
            optional connection information
        """
        AsyncConnection.conn_count += 1
        self.id: str = conn_id
        self.received: int = 0
        self.sent: int = 0
        self.last_message = None
        self.subscription = subscription
        self.conn: Union[ClientConnection, aiohttp.ClientSession] = None
        self.created: float = time.time()
        self.connects: int = 0
        self.watchdog_trips: int = 0
        self._received_before: int = 0
        self._sent_before: int = 0
        _LIVE.add(self)

    @property
    def uuid(self):
        return self.id

    @asynccontextmanager
    async def connect(self):
        await self._open()
        self.connects += 1
        try:
            yield self
        finally:
            await self.close()

    def _reset_counters(self):
        self._received_before += self.received
        self._sent_before += self.sent
        self.received = 0
        self.sent = 0
        self.last_message = None

    def record_watchdog_trip(self):
        self.watchdog_trips += 1

    @property
    def stats(self) -> ConnectionStats:
        """Read-only snapshot. Never raises: a report that cannot be taken is worse than a stale one."""
        try:
            is_open = bool(self.is_open)
        except NotImplementedError:
            is_open = False
        return ConnectionStats(id=self.id, created=self.created, connects=self.connects,
                               reconnects=max(self.connects - 1, 0), watchdog_trips=self.watchdog_trips,
                               received=self._received_before + self.received,
                               sent=self._sent_before + self.sent,
                               last_message=self.last_message, open=is_open)

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

        if self.raw_data_callback is not None:
            await self.raw_data_callback.on_close(self)


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
            self._reset_counters()

    async def read(self, address: str, header=None, params=None, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        LOG.debug("%s: requesting data from %s", self.id, address)
        while True:
            async with self.conn.get(address, headers=header, params=params, proxy=self.proxy) as response:
                data = await response.text()
                self.last_message = time.time()
                self.received += 1
                if response.status == 429 and retry_count:
                    LOG.warning("%s: encountered a rate limit for address %s, retrying in 60 seconds", self.id, address)
                    retry_count -= 1
                    if retry_count < 0:
                        self._handle_error(response, data)
                    await asyncio.sleep(retry_delay)
                    continue
                self._handle_error(response, data)
                if self.raw_data_callback is not None:
                    await self.raw_data_callback.on_http(self, address, params, header, data, self.last_message)
                return data

    async def write(self, address: str, msg: str, header=None, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        while True:
            async with self.conn.post(address, data=msg, headers=header) as response:
                self.sent += 1
                data = await response.read()
                if response.status == 429 and retry_count:
                    LOG.warning("%s: encountered a rate limit for address %s, retrying in 60 seconds", self.id, address)
                    retry_count -= 1
                    if retry_count < 0:
                        self._handle_error(response, data)
                    await asyncio.sleep(retry_delay)
                    continue
                self._handle_error(response, data)
                if self.raw_data_callback is not None:
                    await self.raw_data_callback.on_http_post(self, address, msg, data, time.time())
                return data

    async def delete(self, address: str, header=None, retry_count=0, retry_delay=60) -> str:
        if not self.is_open:
            await self._open()

        while True:
            async with self.conn.delete(address, headers=header) as response:
                self.sent += 1
                data = await response.read()
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
        super().__init__(conn_id, proxy)
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
                if response.status != 429:
                    response.raise_for_status()
                    if self.raw_data_callback is not None:
                        await self.raw_data_callback.on_http_poll(self, address, header, data, self.last_message)
                    return data
            LOG.warning("%s: encountered a rate limit for address %s, retrying in %f seconds", self.id, address, self.delay)
            await asyncio.sleep(self.delay)

    async def read(self, header=None) -> AsyncIterable[str]:
        while True:
            for addr in self.address:
                yield await self._read_address(addr, header)
            await asyncio.sleep(self.sleep)


class WSAsyncConn(AsyncConnection):

    def __init__(self, address: str, conn_id: str, subscription=None, **kwargs):
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
        super().__init__(f'{conn_id}.ws.{self.conn_count}', subscription=subscription)
        self.ws_kwargs = kwargs

    @property
    def is_open(self) -> bool:
        return self.conn and not self.conn.state == State.CLOSED

    async def _open(self):
        if self.is_open:
            LOG.warning('%s: websocket already open', self.id)
        else:
            LOG.debug('%s: connecting to %s', self.id, self.address)
            self.conn = await connect(self.address, **self.ws_kwargs)
            if self.raw_data_callback is not None:
                await self.raw_data_callback.on_ws_open(self, time.time())
        self._reset_counters()

    async def read(self) -> AsyncIterable:
        if not self.is_open:
            LOG.error('%s: connection closed in read()', id(self))
            raise ConnectionClosed
        async for data in self.conn:
            self.received += 1
            self.last_message = time.time()
            if self.raw_data_callback is not None:
                await self.raw_data_callback.on_ws_message(self, data, self.last_message)
            yield data

    async def write(self, data: str):
        if not self.is_open:
            raise ConnectionClosed

        await self.conn.send(data)
        self.sent += 1
        if self.raw_data_callback is not None:
            await self.raw_data_callback.on_ws_send(self, data, time.time())


@dataclass
class WebsocketEndpoint:
    address: str
    sandbox: str = None
    instrument_filter: str = None
    channel_filter: str = None
    limit: int = None
    options: dict = None

    def __post_init__(self):
        defaults = {'ping_interval': 20, 'ping_timeout': 60, 'max_size': None, 'max_queue': 1024}
        if self.options:
            defaults.update(self.options)
        self.options = defaults

    def subscription_filter(self, sub: dict) -> dict:
        if not self.instrument_filter and not self.channel_filter:
            return sub
        ret = {}
        for chan, syms in sub.items():
            if self.channel_filter and chan not in self.channel_filter:
                continue
            ret[chan] = []
            if not self.instrument_filter:
                ret[chan].extend(sub[chan])
            elif callable(self.instrument_filter):
                # some venues split endpoints on more than one attribute
                ret[chan].extend([s for s in syms if self.instrument_filter(str_to_symbol(s))])
            else:
                if self.instrument_filter[0] == 'TYPE':
                    ret[chan].extend([s for s in syms if str_to_symbol(s).type in self.instrument_filter[1]])
                elif self.instrument_filter[0] == 'QUOTE':
                    ret[chan].extend([s for s in syms if str_to_symbol(s).quote in self.instrument_filter[1]])
                else:
                    raise ValueError('Invalid instrument filter type specified')
        return ret

    def get_address(self, sandbox=False):
        if sandbox and self.sandbox:
            return self.sandbox
        return self.address


@dataclass
class Routes:
    instruments: Union[str, list]
    currencies: str = None
    funding: str = None
    open_interest: str = None
    liquidations: str = None
    l2book: str = None
    l3book: str = None


@dataclass
class RestEndpoint:
    address: str
    sandbox: str = None
    instrument_filter: str = None
    routes: Routes = None

    def route(self, ep, sandbox=False):
        endpoint = self.routes.__getattribute__(ep)
        api = self.sandbox if sandbox and self.sandbox else self.address
        return api + endpoint if isinstance(endpoint, str) else [api + e for e in endpoint]
