'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from contextlib import asynccontextmanager

import websockets


class AsyncConnection:
    def __init__(self, address: str, **kwargs):
        self.address = address
        self.kwargs = kwargs
        self.conn = None

        if self.address[:2] == 'ws':
            self.conn_type = "ws"
        else:
            raise ValueError("Invalid connection type, ensure address contains valid protocol")

    @asynccontextmanager
    async def connect(self):
        if self.conn_type == "ws":
            self.conn = await websockets.connect(self.address, **self.kwargs)

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
        async for data in self.conn:
            yield data

    @property
    def open(self):
        if self.conn:
            return self.conn.open
        return False
