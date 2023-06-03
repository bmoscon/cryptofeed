'''
Copyright (C) 2017-2023 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from cryptofeed.defines import ASK, BID
from datetime import datetime as dt, timedelta
from decimal import Decimal

from cryptofeed.exchanges import Deribit


d = Deribit()


def teardown_module(module):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    
    loop.run_until_complete(d.shutdown())


class TestDeribitRest:
    def test_trade(self):
        ret = []
        for data in d.trades_sync('BTC-USD-PERP'):
            ret.extend(data)
        assert len(ret) > 1


    def test_trades(self):
        ret = []
        start = dt.utcnow() - timedelta(days=5)
        end = dt.utcnow() - timedelta(days=4, hours=18)

        for data in d.trades_sync('BTC-USD-PERP', start=start, end=end):
            ret.extend(data)
        assert len(ret) > 0
        assert ret[0]['symbol'] == 'BTC-USD-PERP'
        assert isinstance(ret[0]['price'], Decimal)
        assert isinstance(ret[0]['amount'], Decimal)


    def test_l2_book(self):
        ret = d.l2_book_sync('BTC-USD-PERP')
        assert len(ret.book[BID]) > 0
        assert len(ret.book[ASK]) > 0
