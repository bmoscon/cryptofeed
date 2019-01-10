'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time


class AggregateCallback:
    def __init__(self, handler, *args, **kwargs):
        self.handler = handler


class Throttle(AggregateCallback):
    def __init__(self, *args, timer=60, **kwargs):
        super().__init__(*args, **kwargs)
        self.timer = timer
        self.last_update = 0

    async def __call__(self, **kwargs):
        now = time.time()
        if now - self.last_update > self.timer:
            self.last_update = now
            await self.handler(**kwargs)
