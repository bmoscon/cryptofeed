'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect


class Callback:
    def __init__(self, callback):
        self.callback = callback
        self.is_async = inspect.iscoroutinefunction(callback)

    async def __call__(self, obj, receipt_timestamp):
        if self.callback is None:
            return
        elif self.is_async:
            await self.callback(obj, receipt_timestamp)
        else:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.callback, (obj, receipt_timestamp))


class TradeCallback(Callback):
    pass


class TickerCallback(Callback):
    pass


class BookCallback(Callback):
    pass


class CandleCallback(Callback):
    pass


class LiquidationCallback(Callback):
    pass


class OpenInterestCallback(Callback):
    pass


class FundingCallback(Callback):
    pass


class IndexCallback(Callback):
    pass


class OrderInfoCallback(Callback):
    pass


class BalancesCallback(Callback):
    pass


class TransactionsCallback(Callback):
    pass


class UserFillsCallback(Callback):
    pass


class L1BookCallback(Callback):
    pass
