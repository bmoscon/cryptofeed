'''
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from cryptofeed.defines import ASK, BID
from cryptofeed.exchanges import dYdX


d = dYdX()


def teardown_module(module):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    loop.run_until_complete(d.shutdown())


class TestDYDXRest:
    def test_trade(self):
        ret = []
        for data in d.trades_sync('BTC-USD-PERP'):
            ret.extend(data)
        assert len(ret) > 1

    def test_l2_book(self):
        ret = d.l2_book_sync('BTC-USD-PERP')
        assert len(ret.book[BID]) > 0
        assert len(ret.book[ASK]) > 0
