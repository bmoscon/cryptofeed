'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from contextlib import asynccontextmanager
from typing import Union, List
import uuid

import aiohttp
import websockets


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
        self.__sleep = sleep
        self.__delay = delay
        self.__identifier = f"{identifier}-{str(uuid.uuid4())[:6]}"

        if isinstance(address, str) and self.address[:2] == 'ws':
            self.conn_type = "ws"
        elif isinstance(address, list) and all(addr[:5] == 'https' for addr in address):
            self.conn_type = 'https'
        elif isinstance(address, str) and address[:5] == 'https':
            self.conn_type = 'https'
        else:
            raise ValueError("Invalid connection type, ensure address contains valid protocol")

    @asynccontextmanager
    async def connect(self):
        if self.conn_type == "ws":
            self.conn = await websockets.connect(self.address, **self.kwargs)
        else:
            self.conn = aiohttp.ClientSession()
        try:
            yield self
        finally:
            if self.conn:
                await self.conn.close()
                self.conn = None

    async def send(self, msg: str):
        return await self.conn.send(msg)

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def read(self):
        if self.conn_type == 'ws':
            async for data in self.conn:
                yield data
        elif self.conn_type == 'https':
            while True:
                for addr in self.address:
                    async with self.conn.get(addr) as response:
                        response.raise_for_status()
                        data = await response.text()
                        yield data
                    await asyncio.sleep(self.__sleep)

    @property
    def open(self):
        if self.conn:
            if self.conn_type == "ws":
                return self.conn.open
            elif self.conn_type == 'https':
                return not self.conn.closed
        return False

    @property
    def uuid(self):
        return self.__identifier

    @property
    def delay(self):
        return self.__delay
