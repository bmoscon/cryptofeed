'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from asyncio.queues import Queue
from contextlib import asynccontextmanager
from decimal import Decimal

from cryptofeed.backends._util import book_convert, book_delta_convert
from cryptofeed.defines import BID, ASK


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


class BackendBookCallback:
    async def __call__(self, *, feed: str, symbol: str, book: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=self.numeric_type)
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendBookDeltaCallback:
    async def __call__(self, *, feed: str, symbol: str, delta: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendTradeCallback:
    async def __call__(self, *, feed: str, symbol: str, side: str, amount: Decimal, price: Decimal, order_id: str = None, timestamp: float, receipt_timestamp: float, order_type: str = None):
        data = {'feed': feed, 'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price), 'order_type': order_type, 'id': order_id}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendFundingCallback:
    async def __call__(self, *, feed, symbol, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])
        kwargs['feed'] = feed
        kwargs['symbol'] = symbol
        timestamp = kwargs.get('timestamp')
        receipt_timestamp = kwargs.get('receipt_timestamp')

        await self.write(feed, symbol, timestamp, receipt_timestamp, kwargs)


class BackendTickerCallback:
    async def __call__(self, *, feed: str, symbol: str, bid: Decimal, ask: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'bid': self.numeric_type(bid), 'ask': self.numeric_type(ask), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendOpenInterestCallback:
    async def __call__(self, *, feed: str, symbol: str, open_interest: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'open_interest': self.numeric_type(open_interest), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendFuturesIndexCallback:
    async def __call__(self, *, feed: str, symbol: str, futures_index: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'futures_index': self.numeric_type(futures_index), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendLiquidationsCallback:
    async def __call__(self, *, feed: str, symbol: str, side: str, leaves_qty: Decimal, price: Decimal, order_id: str, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'side': side, 'leaves_qty': self.numeric_type(leaves_qty), 'price': self.numeric_type(price), 'order_id': order_id if order_id else "None", 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendMarketInfoCallback:
    async def __call__(self, *, feed: str, symbol: str, timestamp: float, **kwargs):
        kwargs['feed'] = feed
        kwargs['symbol'] = symbol
        kwargs['timestamp'] = timestamp
        await self.write(feed, symbol, timestamp, timestamp, kwargs)


class BackendCandlesCallback:
    async def __call__(self, *, feed: str, symbol: str, start: float, stop: float, interval: str, trades: int, open_price: Decimal, close_price: Decimal, high_price: Decimal, low_price: Decimal, volume: Decimal, closed: bool, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp,
                'start': start, 'stop': stop, 'interval': interval, 'trades': trades, 'open_price': self.numeric_type(open_price),
                'close_price': self.numeric_type(close_price), 'high_price': self.numeric_type(high_price), 'low_price': self.numeric_type(low_price),
                'volume': self.numeric_type(volume), 'closed': str(closed)
                }
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)
