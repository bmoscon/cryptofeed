'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import atexit
import logging
from datetime import datetime
from collections import defaultdict

from aiofile import AIOFile


class AsyncFileCallback:
    def __init__(self, path, length=10000, rotate=1024 * 1024 * 100):
        self.path = path
        self.length = length
        self.data = defaultdict(list)
        self.rotate = rotate
        self.count = defaultdict(int)
        self.pointer = defaultdict(int)
        self.ymd = defaultdict(str)
        atexit.register(self.__del__)

    def __del__(self):
        for uuid in list(self.data.keys()):
            p = f"{self.path}/{self.ymd[uuid]}_{uuid}.json"
            with open(p, 'a') as fp:
                fp.write("\n".join(self.data[uuid]))

    async def write(self, uuid):
        #print([uuid, self.pointer[uuid]])
        if uuid not in self.pointer.keys():
           self.ymd[uuid] = str(datetime.now()).replace('-', "").replace(' ', "_").replace(':', "").split('.')[0]

        p = f"{self.path}/{self.ymd[uuid]}_{uuid}.json"
        logging.info(p)
        async with AIOFile(p, mode='a') as fp:
            r = await fp.write("\n".join(self.data[uuid]) + "\n", offset=self.pointer[uuid])
            self.pointer[uuid] += r
            self.data[uuid] = []


        if self.pointer[uuid] >= self.rotate:
            self.ymd[uuid] = str(datetime.utcnow()).replace('-', "").replace(' ',"_").replace(':',"").split('.')[0]
            self.count[uuid] += 1
            self.pointer[uuid] = 0

    async def __call__(self, data: str, timestamp: float, uuid: str):
        self.data[uuid].append(data)
        if len(self.data[uuid]) >= self.length:
            await self.write(uuid)
