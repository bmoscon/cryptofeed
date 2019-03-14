'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
from decimal import Decimal


class AggregateCallback:
    def __init__(self, handler, *args, **kwargs):
        self.handler = handler


class Throttle(AggregateCallback):
    """
    Wraps a callback and throttles updates based on `window`. Will allow
    1 update per `window` interval; all others are dropped
    """

    def __init__(self, *args, window=60, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = window
        self.last_update = 0

    async def __call__(self, **kwargs):
        now = time.time()
        if now - self.last_update > self.window:
            self.last_update = now
            await self.handler(**kwargs)


class OHLCV(AggregateCallback):
    """
    Aggregate trades and calculate OHLCV for time window
    window is in seconds, defaults to 300 seconds (5 minutes)
    """

    def __init__(self, *args, window=300, **kwargs):
        super().__init__(*args, **kwargs)
        self.window = window
        self.last_update = time.time()
        self.data = {}

    def _agg(self, pair, amount, price):
        if pair not in self.data:
            self.data[pair] = {'open': price, 'high': price, 'low': price, 'close': price, 'volume': Decimal(0), 'vwap': Decimal(0)}

        self.data[pair]['close'] = price
        self.data[pair]['volume'] += amount
        if price > self.data[pair]['high']:
            self.data[pair]['high'] = price
        if price < self.data[pair]['low']:
            self.data[pair]['low'] = price
        self.data[pair]['vwap'] += price * amount

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        now = time.time()
        if now - self.last_update > self.window:
            self.last_update = now
            for p in self.data:
                self.data[p]['vwap'] /= self.data[p]['volume']
            await self.handler(data=self.data)
            self.data = {}

        self._agg(pair, amount, price)


class CustomAggregate(AggregateCallback):
    def __init__(self, *args, window=30, aggregator=None, init=None, **kwargs):
        """
        aggregator is a function pointer to the aggregator function. The aggregator will be called with
        a dictionary of internal state (the aggregator will define it), and the data from the cryptofeed callback (trade, book, etc).
        init is a function pointer that will be called at the start of each time window, with the internal state.
        This can be used to clear the internal state or
        do other appropriate work (if any).
        """
        super().__init__(*args, **kwargs)
        self.window = window
        self.last_update = time.time()
        self.agg = aggregator
        self.init = init
        self.data = {}
        self.init(self.data)

    async def __call__(self, **kwargs):
        now = time.time()
        if now - self.last_update > self.window:
            self.last_update = now
            await self.handler(data=self.data)
            self.init(self.data)

        self.agg(self.data, **kwargs)
