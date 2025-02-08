'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
@Author: bastien.enjalbert@gmail.com
'''
import asyncio
from decimal import Decimal

from cryptofeed.exchanges import OKX
from cryptofeed.types import Candle

o = OKX()


def teardown_module(module):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    loop.run_until_complete(o.shutdown())


class TestOKXRest:

    def test_candles(self):
        expected = Candle(
            o.id,
            'BTC-USDT',
            1609459200.0,
            1609459260.0,
            '1m',
            None,
            Decimal('28914.8'),      # open
            Decimal('28959.1'),      # close
            Decimal('28959.1'),      # high
            Decimal('28914.8'),      # low
            Decimal('13.22459039'),  # volume
            True,
            1609459200.0
        )
        ret = []
        for data in o.candles_sync('BTC-USDT', start='2021-01-01 00:00:00', end='2021-01-01 00:00:01', interval='1m'):
            ret.extend(data)

        assert len(ret) == 1
        assert ret[0] == expected