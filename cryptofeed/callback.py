'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect


class Callback:
    def __init__(self, callback):
        if callback is not None and not inspect.iscoroutinefunction(callback):
            raise TypeError('callbacks must be coroutine functions. Wrap synchronous callables in ExecutorCallback')
        self.callback = callback

    async def __call__(self, obj, receipt_timestamp: float):
        if self.callback is None:
            return
        await self.callback(obj, receipt_timestamp)


class ExecutorCallback:
    def __init__(self, callback):
        if not callable(callback) or inspect.iscoroutinefunction(callback):
            raise TypeError('ExecutorCallback wraps synchronous callables only')
        self.callback = callback

    async def __call__(self, *args):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.callback, *args)


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
