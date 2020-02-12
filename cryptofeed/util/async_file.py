'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import atexit
from collections import defaultdict

import aiofiles
import aiofiles.os


class AsyncFileCallback:
    def __init__(self, path, length=10000, rotate=1024 * 1024 * 100):
        self.path = path
        self.length = length
        self.data = defaultdict(list)
        self.rotate = rotate
        self.count = defaultdict(int)
        atexit.register(self.__del__)

    def __del__(self):
        for uuid in list(self.data.keys()):
            with open(f"{self.path}/{uuid}.{self.count[uuid]}", 'a') as fp:
                fp.write("\n".join(self.data[uuid]))

    async def write(self, uuid):
        p = f"{self.path}/{uuid}.{self.count[uuid]}"
        async with aiofiles.open(p, mode='a') as fp:
            await fp.write("\n".join(self.data[uuid]))
        self.data[uuid] = []

        stats = await aiofiles.os.stat(p)
        if stats.st_size >= self.rotate:
            self.count[uuid] += 1

    async def __call__(self, data: str, timestamp: float, uuid: str):
        self.data[uuid].append(f"{timestamp}: {data}")
        if len(self.data[uuid]) >= self.length:
            await self.write(uuid)
