'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect
from decimal import Decimal


class Callback(object):
    def __init__(self, callback):
        self.callback = callback
        self.is_async = inspect.iscoroutinefunction(callback)

    async def __call__(self, *args, **kwargs):
        if self.callback is None:
            pass
        else:
            raise NotImplementedError


class TradeCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal):
        if self.is_async:
            await self.callback(feed, pair, side, amount, price)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, feed, pair, side, amount, price)


class TickerCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, bid:  Decimal, ask: Decimal):
        if self.is_async:
            await self.callback(feed, pair, bid, ask)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, feed, pair, bid, ask)


class BookCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, book: dict):
        if self.is_async:
            await self.callback(feed, pair, book)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, feed, pair, book)


class VolumeCallback(Callback):
    async def __call__(self, **kwargs):
        if self.is_async:
            await self.callback(**kwargs)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, **kwargs)
