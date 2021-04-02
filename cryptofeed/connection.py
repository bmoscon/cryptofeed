'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from contextlib import asynccontextmanager
import logging
import time
from typing import Callable, Union, List
import uuid

import aiohttp
import websockets


LOG = logging.getLogger('feedhandler')


class AsyncConnection:
    def __init__(self, address: Union[str, List[str]], identifier: str, delay: float = 1.0, sleep: float = 0.0, **kwargs):
        """
        address: str, or list of str
            address to be used to create the connection. A list of addresses is only valid for HTTPS connections.
            The address protocol (wss or https) will be used to determine the connection type.

        identifier: str
            unique string used to identify the connection.

        delay: float
            time in seconds to delay between reconnects (due to errors).

        sleep: float
            time in seconds to delay between requests.

        kwargs:
            passed into the websocket connection.
        """
        self.address = address
        self.kwargs = kwargs
        self.conn = None
        self.session = None
        self.raw_cb = None
        self.__sleep = sleep
        self.__delay = delay
        self.__identifier = f"{identifier}-{str(uuid.uuid4())[:6]}"

        if isinstance(address, str) and self.address[:2] == 'ws':
            self.conn_type = "ws"
        elif isinstance(address, list) and all(addr[:5] == 'https' for addr in address):
            self.conn_type = 'https'
        elif isinstance(address, str) and address[:5] == 'https':
            self.conn_type = 'https'
            self.address = [address]
        else:
            raise ValueError("Invalid connection type, ensure address contains valid protocol")

    @asynccontextmanager
    async def connect(self):
        self.session = aiohttp.ClientSession()
        if self.conn_type == "ws":
            if self.raw_cb:
                await self.raw_cb(None, time.time(), self.uuid, connect=self.address)
            LOG.debug("Connecting (websocket) to %s", self.address)
            self.conn = await websockets.connect(self.address, **self.kwargs)

        try:
            yield self
        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None
            if self.session:
                await self.session.close()
                self.session = None

    async def send(self, msg: str):
        if self.raw_cb:
            await self.raw_cb(msg, time.time(), self.uuid, send=self.address)
        return await self.conn.send(msg)

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
        if self.session:
            await self.session.close()
            self.session = None

    async def read(self):
        if self.conn_type == 'ws':
            if self.raw_cb:
                async for data in self.conn:
                    await self.raw_cb(data, time.time(), self.uuid)
                    yield data
            else:
                async for data in self.conn:
                    yield data

        elif self.conn_type == 'https':
            while True:
                for addr in self.address:
                    async with self.session.get(addr) as response:
                        data = await response.text()
                        if self.raw_cb:
                            await self.raw_cb(data, time.time(), self.uuid, endpoint=addr)
                        response.raise_for_status()
                        yield data
                    await asyncio.sleep(self.__sleep)

    async def get(self, uri: str):
        async with self.session.get(uri) as response:
            data = await response.text()
            if self.raw_cb:
                await self.raw_cb(data, time.time(), self.uuid, endpoint=uri)
            response.raise_for_status()

            return data

    def set_raw_data_callback(self, raw_data_cb: Callable):
        self.raw_cb = raw_data_cb

    @property
    def open(self):
        if self.conn:
            if self.conn_type == "ws":
                return self.conn.open
            elif self.conn_type == 'https':
                return not self.session.closed
        return False

    @property
    def uuid(self):
        return self.__identifier

    @property
    def delay(self):
        return self.__delay
