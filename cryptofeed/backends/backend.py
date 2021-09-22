'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from asyncio.queues import Queue
from contextlib import asynccontextmanager


class BackendQueue:
    def start(self, loop: asyncio.AbstractEventLoop):
        if hasattr(self, 'started') and self.started:
            # prevent a backend callback from starting more than 1 writer and creating more than 1 queue
            return
        self.queue = Queue()
        loop.create_task(self.writer())
        self.started = True

    async def writer(self):
        raise NotImplementedError

    @asynccontextmanager
    async def read_queue(self):
        update = await self.queue.get()
        yield update
        self.queue.task_done()

    @asynccontextmanager
    async def read_many_queue(self, count: int):
        ret = []
        counter = 0
        while counter < count:
            update = await self.queue.get()
            ret.append(update)
            counter += 1

        yield ret

        for _ in range(count):
            self.queue.task_done()


class BackendCallback:
    async def __call__(self, dtype, receipt_timestamp: float):
        data = dtype.to_dict(as_type=self.numeric_type)
        data['receipt_timestamp'] = receipt_timestamp
        await self.write(data)


class BackendBookCallback:
    async def __call__(self, book, receipt_timestamp: float):
        if self.snapshots_only:
            data = book.to_dict(as_type=self.numeric_type)
            del data['delta']
            data['receipt_timestamp'] = receipt_timestamp
            await self.write(data)
        else:
            data = book.to_dict(delta=book.delta is not None, as_type=self.numeric_type)
            data['receipt_timestamp'] = receipt_timestamp
            if book.delta is None:
                del data['delta']
            await self.write(data)
