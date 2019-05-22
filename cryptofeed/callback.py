'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

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
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await super().__call__(feed, pair, order_id, timestamp, side, amount, price)


class TickerCallback(Callback):
    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal):
        await super().__call__(feed, pair, bid, ask)


class BookCallback(Callback):
    """
    For full L2/L3 book updates
    """
    async def __call__(self, *, feed: str, pair: str, book: dict, timestamp):
        await super().__call__(feed, pair, book, timestamp)


class BookUpdateCallback(Callback):
    """
    For Book Deltas
    """
    async def __call__(self, *, feed: str, pair: str, delta: dict, timestamp):
        """
        Delta is in format of:
        {
            BID: {
                ADD: [(price, size), (price, size), ...],
                DEL: [price, price, price, ...]
                UPD: [(price, size), (price, size), ...]
            },
            ASK: {
                ADD: [(price, size), (price, size), ...],
                DEL: [price, price, price, ...]
                UPD: [(price, size), (price, size), ...]
            }
        }

        ADD - these tuples should simply be inserted.
        DEL - price levels should be deleted
        UPD - prices should have the quantity set to size (these are not price deltas)
        """
        await super().__call__(feed, pair, delta, timestamp)


class VolumeCallback(Callback):
    pass


class FundingCallback(Callback):
    pass
