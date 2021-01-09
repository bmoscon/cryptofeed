'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
from decimal import Decimal

import numpy as np


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

    def _agg(self, symbol, amount, price):
        if symbol not in self.data:
            self.data[symbol] = {'open': price, 'high': price, 'low': price,
                                 'close': price, 'volume': Decimal(0), 'vwap': Decimal(0)}

        self.data[symbol]['close'] = price
        self.data[symbol]['volume'] += amount
        if price > self.data[symbol]['high']:
            self.data[symbol]['high'] = price
        if price < self.data[symbol]['low']:
            self.data[symbol]['low'] = price
        self.data[symbol]['vwap'] += price * amount

    async def __call__(self, *, feed: str, symbol: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, receipt_timestamp: float, order_type=None):
        now = time.time()
        if now - self.last_update > self.window:
            self.last_update = now
            for p in self.data:
                self.data[p]['vwap'] /= self.data[p]['volume']
            await self.handler(data=self.data)
            self.data = {}

        self._agg(symbol, amount, price)


class RenkoFixed(AggregateCallback):
    """
    Aggregate trades into Renko bricks with fixed size
    brick size is in points, default to 10 (change to ticks later?)
    """

    def __init__(self, *args, brick_size=10, **kwargs):
        super().__init__(*args, **kwargs)
        self.brick_size = brick_size
        self.new_brick = True
        self.data = {}
        self.brick_open = None
        self.brick_close = None
        self.brick_high = None
        self.brick_low = None
        self.prev_direction = 0

    @staticmethod
    def greater_abs(minus, plus):
        return minus if -minus > plus else plus

    def _agg(self, symbol, price):
        if symbol not in self.data:
            self.brick_open = price
            self.brick_high = price
            self.brick_low = price
            self.data[symbol] = {'brick_open': price, 'brick_close': price}

        self.brick_low = np.min([self.brick_low, price])
        self.brick_high = np.max([self.brick_high, price])

        # Reversal brick logic
        if self.prev_direction == 0:
            self.minus_diff = self.brick_low - self.brick_open
            self.plus_diff = self.brick_high - self.brick_open
        elif self.prev_direction == 1:
            self.minus_diff = self.brick_low - self.brick_open
            self.plus_diff = self.brick_high - self.brick_close
        elif self.prev_direction == -1:
            self.minus_diff = self.brick_low - self.brick_close
            self.plus_diff = self.brick_high - self.brick_open
        self.greater_diff = self.greater_abs(self.minus_diff, self.plus_diff)

        if abs(self.greater_diff) >= self.brick_size:
            self.new_brick = True
            self.new_direction = np.sign(self.greater_diff)
            same = self.new_direction == self.prev_direction
            if same:
                self.brick_open = self.brick_close
            self.data[symbol]['brick_open'] = self.brick_open
            self.brick_close = price
            self.data[symbol]['brick_close'] = self.brick_close
            self.brick_high = self.brick_low = self.brick_close
            self.prev_direction = self.new_direction

        else:
            self.new_brick = False

    async def __call__(self, *, feed: str, symbol: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, receipt_timestamp: float, order_type=None):
        if self.new_brick:
            await self.handler(data=self.data)
        self._agg(symbol, price)


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
