'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import atexit
from collections import defaultdict
from cryptofeed.exceptions import ConnectionClosed
from time import time

from cryptofeed.connection import HTTPAsyncConn, HTTPPoll, HTTPSync, WSAsyncConn
import functools
import ast

from aiofile import AIOFile

from cryptofeed.defines import HUOBI, UPBIT, OKEX, OKCOIN


def bytes_string_to_bytes(string):
    tree = ast.parse(string)
    return tree.body[0].value.s


def playback(feed, filename):
    return asyncio.run(_playback(feed, filename))


async def _playback(feed, filename):
    callbacks = defaultdict(int)

    class FakeWS:
        def __init__(self, filename):
            self.conn_type = 'wss'
            self.filename = filename
            self.cache = None
            self.uuid = "1"

        async def send(self, *args, **kwargs):
            pass

        async def get(self, url):
            if not self.cache:
                self.cache = defaultdict(list)
                with open(self.filename, 'r') as fp:
                    line = fp.readline()
                    while line:
                        if line.startswith('http'):
                            file_url, data = line.split(' -> ')
                            _, msg = data.split(": ", 1)
                            self.cache[file_url].append(msg)
                        line = fp.readline()
            return self.cache[url].pop(0)

    async def internal_cb(*args, **kwargs):
        callbacks[kwargs['cb_type']] += 1

    for cb_type, handler in feed.callbacks.items():
        f = functools.partial(internal_cb, cb_type=cb_type)
        handler.append(f)

    ws = FakeWS(filename)
    for _, sub, handler in feed.connect():
        await sub(ws)

    counter = 0
    with open(filename, 'r') as fp:
        # skip header
        next(fp)
        for line in fp:
            if line == "\n":
                continue
            start = line[:3]
            if start == 'wss':
                continue
            if start == 'htt':
                counter += 1
                continue

            try:
                timestamp, message = line.split(": ", 1)
                counter += 1

                if OKCOIN in filename or OKEX in filename:
                    if message.startswith('b\'') or message.startswith('b"'):
                        message = bytes_string_to_bytes(message)
                elif HUOBI in filename:
                    message = bytes_string_to_bytes(message)
                elif UPBIT in filename:
                    if message.startswith('b\'') or message.startswith('b"'):
                        message = message.strip()[2:-1]

                await handler(message, ws, timestamp)
            except Exception:
                print("Playback failed on message:", message)
                raise

    return {'messages_processed': counter, 'callbacks': dict(callbacks)}


class AsyncFileCallback:
    def __init__(self, path, length=10000, rotate=1024 * 1024 * 100):
        self.path = path
        self.length = length
        self.data = defaultdict(list)
        self.rotate = rotate
        self.count = defaultdict(int)
        self.pointer = defaultdict(int)
        atexit.register(self.__del__)

    def __del__(self):
        self.stop()

    def stop(self):
        for uuid in list(self.data.keys()):
            with open(f"{self.path}/{uuid}.{self.count[uuid]}", 'a') as fp:
                fp.write("\n".join(self.data[uuid]) + "\n")
                self.data[uuid] = []
                fp.flush()

    def set_header(self, uuid, data):
        self.data[uuid].append(f"configuration: {data}")

    async def write(self, uuid):
        p = f"{self.path}/{uuid}.{self.count[uuid]}"
        async with AIOFile(p, mode='a') as fp:
            r = await fp.write("\n".join(self.data[uuid]) + "\n", offset=self.pointer[uuid])
            self.pointer[uuid] += r
            self.data[uuid] = []
            await fp.fsync()

        if self.pointer[uuid] >= self.rotate:
            self.count[uuid] += 1
            self.pointer[uuid] = 0

    async def __call__(self, data: str, timestamp: float, uuid: str, endpoint: str = None, send: str = None, connect: str = None):
        if endpoint:
            self.data[uuid].append(f"{endpoint} -> {timestamp}: {data}")
        elif send:
            self.data[uuid].append(f"{send} <- {timestamp}: {data}")
        elif connect:
            self.data[uuid].append(f"{connect} <-> {timestamp}")
        else:
            self.data[uuid].append(f"{timestamp}: {data}")

        if len(self.data[uuid]) >= self.length:
            await asyncio.create_task(self.write(uuid))

    def sync_callback(self, data: str, timestamp: float, uuid: str, endpoint: str = None, send: str = None, connect: str = None):
        if endpoint:
            self.data[uuid].append(f"{endpoint} -> {timestamp}: {data}")
        elif send:
            self.data[uuid].append(f"{send} <- {timestamp}: {data}")
        elif connect:
            self.data[uuid].append(f"{connect} <-> {timestamp}")
        else:
            self.data[uuid].append(f"{timestamp}: {data}")


class HTTPSyncRaw(HTTPSync):
    def __init__(self, cb, id):
        self.cb = cb
        self.id = id + ".symbol"

    def read(self, address: str, **kwargs):
        print("HELLO")
        data = super().read(address, **kwargs)
        self.cb.sync_callback(data, time(), self.id)
        return data


class HTTPAsyncConnRaw(HTTPAsyncConn):
    def __init__(self, cb, id):
        super().__init__(id)
        self.cb = cb

    async def read(self, address):
        data = await super().read(address)
        await self.cb(data, self.last_message, self.id, endpoint=address)
        return data


class HTTPPollRaw(HTTPPoll):
    def __init__(self, cb, address, sleep, delay, id):
        super().__init__(address, id, delay, sleep)
        self.cb = cb
        self.address = address
        self.sleep = sleep
        self.delay = delay
        self.id = id

    async def read(self):
        while True:
            for addr in self.address:
                if not self.is_open:
                    raise ConnectionClosed
                async with self.conn.get(addr) as response:
                    response.raise_for_status()
                    data = await response.text()
                    self.received += 1
                    self.last_message = time()
                    await self.cb(data, self.last_message, self.uuid)
                    yield data
                    await asyncio.sleep(self.sleep)
            await asyncio.sleep(self.delay)


class WSAsyncConnRaw(WSAsyncConn):
    def __init__(self, cb, address, id, ws_options):
        super().__init__(address, id, **ws_options)
        self.cb = cb
        self.address = address
        self.id = id
        self.ws_kwargs = ws_options

    async def _open(self):
        await self.cb(None, time(), self.id, connect=self.address)
        await super()._open()

    async def read(self):
        if not self.is_open:
            raise ConnectionClosed
        async for data in self.conn:
            self.received += 1
            self.last_message = time()
            await self.cb(data, self.last_message, self.uuid)
            yield data

    async def write(self, data: str):
        await self.cb(data, time(), self.id, send=self.address)
        await super().write(data)
