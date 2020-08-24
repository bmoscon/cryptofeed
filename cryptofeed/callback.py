'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect
from decimal import Decimal


class Callback:
    def __init__(self, callback):
        self.callback = callback
        self.is_async = inspect.iscoroutinefunction(callback)

    async def __call__(self, *args, **kwargs):
        if self.callback is None:
            return
        elif self.is_async:
            await self.callback(*args, **kwargs)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, *args, **kwargs)


class TradeCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, receipt_timestamp: float):
        await super().__call__(feed, pair, order_id, timestamp, side, amount, price, receipt_timestamp)


class TickerCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float, receipt_timestamp: float):
        await super().__call__(feed, pair, bid, ask, timestamp, receipt_timestamp)


class BookCallback(Callback):
    """
    For full L2/L3 book updates
    """
    async def __call__(self, *, feed: str, pair: str, book: dict, timestamp: float, receipt_timestamp: float):
        await super().__call__(feed, pair, book, timestamp, receipt_timestamp)


class BookUpdateCallback(Callback):
    """
    For Book Deltas
    """
    async def __call__(self, *, feed: str, pair: str, delta: dict, timestamp: float, receipt_timestamp: float):
        """
        Delta is in format of:
        {
            BID: [(price, size), (price, size), ...]
            ASK: [(price, size), (price, size), ...]
        }
        prices with size 0 should be deleted from the book
        """
        await super().__call__(feed, pair, delta, timestamp, receipt_timestamp)


class LiquidationCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, side: str, leaves_qty: Decimal, price: Decimal, order_id: str, timestamp: float, receipt_timestamp: float):
        await super().__call__(feed, pair, side, leaves_qty, price, order_id, timestamp, receipt_timestamp)


class OpenInterestCallback(Callback):
    pass


class VolumeCallback(Callback):
    pass


class FundingCallback(Callback):
    pass
