'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from asyncio.queues import Queue
from contextlib import asynccontextmanager


SHUTDOWN_SENTINEL = 'STOP'


class BackendQueue:
    def start_writer(self, tg: asyncio.TaskGroup, name: str):
        """Spawn a writer as a named task in the feed's TaskGroup.

        A backend callback instance shared across feeds gets exactly one writer,
        owned by the first feed that starts it.
        """
        if getattr(self, 'started', False):
            return None
        self.queue = Queue()
        self.worker = tg.create_task(self.writer(), name=name)
        self.started = True
        return self.worker

    async def stop(self):
        if getattr(self, 'started', False):
            await self.queue.put(SHUTDOWN_SENTINEL)

    async def writer(self):
        raise NotImplementedError

    async def write(self, data):
        await self.queue.put(data)

    @asynccontextmanager
    async def read_queue(self) -> list:
        current_depth = self.queue.qsize()
        if current_depth == 0:
            update = await self.queue.get()
            if update == SHUTDOWN_SENTINEL:
                self.running = False
                yield []
            else:
                yield [update]
            self.queue.task_done()
        else:
            ret = []
            count = 0
            while current_depth > count:
                update = await self.queue.get()
                count += 1
                if update == SHUTDOWN_SENTINEL:
                    self.running = False
                    break
                ret.append(update)

            yield ret

            for _ in range(count):
                self.queue.task_done()


class BackendCallback:
    async def __call__(self, dtype, receipt_timestamp: float):
        data = dtype.to_dict(numeric_type=self.numeric_type, none_to=self.none_to)
        if not dtype.timestamp:
            data['timestamp'] = receipt_timestamp
        data['receipt_timestamp'] = receipt_timestamp
        await self.write(data)


class BackendBookCallback:
    async def _write_snapshot(self, book, receipt_timestamp: float):
        data = book.to_dict(numeric_type=self.numeric_type, none_to=self.none_to)
        del data['delta']
        if not book.timestamp:
            data['timestamp'] = receipt_timestamp
        data['receipt_timestamp'] = receipt_timestamp
        await self.write(data)

    async def __call__(self, book, receipt_timestamp: float):
        if self.snapshots_only:
            await self._write_snapshot(book, receipt_timestamp)
        else:
            data = book.to_dict(delta=book.delta is not None, numeric_type=self.numeric_type, none_to=self.none_to)
            if not book.timestamp:
                data['timestamp'] = receipt_timestamp
            data['receipt_timestamp'] = receipt_timestamp

            if book.delta is None:
                del data['delta']
            else:
                self.snapshot_count[book.symbol] += 1
            await self.write(data)
            if self.snapshot_interval <= self.snapshot_count[book.symbol] and book.delta:
                await self._write_snapshot(book, receipt_timestamp)
                self.snapshot_count[book.symbol] = 0
