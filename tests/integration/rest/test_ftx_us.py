'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import pytest

from cryptofeed.defines import ASK, BID, BUY, SELL
from decimal import Decimal

from cryptofeed.exchanges.ftx_us import FTXUS


f = FTXUS(config='config.yaml')


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(f.shutdown())


class TestFTXUSRest:
    def test_funding(self):
        with pytest.raises(NotImplementedError):
            f.funding_sync('BTC-USD', start='2020-12-10 12:59:10', end='2020-12-11 13:01:33')


    def test_ticker(self):
        ret = f.ticker_sync('BTC-USD')
        assert ret['feed'] == 'FTX_US'
        assert ret['symbol'] == 'BTC-USD'
        assert BID in ret
        assert ASK in ret


    def test_book(self):
        ret = f.l2_book_sync('BTC-USD')

        assert len(ret.book[BID]) > 1
        assert len(ret.book[ASK]) > 1


    def test_trades(self):
        trades = []

        for t in f.trades_sync('BTC-USD'):
            trades.extend(t)

        assert len(trades) > 0
        assert trades[0]['feed'] == 'FTX_US'
        assert trades[0]['symbol'] == 'BTC-USD'


    def test_trades_history(self):
        trades = []

        for t in f.trades_sync('BTC-USD', start='2021-01-01 00:00:00', end='2021-01-01 02:00:00'):
            trades.extend(t)
        trades.reverse()

        assert trades[0] == {'timestamp': 1609459223.978675, 'amount': Decimal('0.0128'), 'feed': 'FTX_US', 'id': 86785, 'price': Decimal('28973.0'), 'side': SELL, 'symbol': 'BTC-USD'}
        assert trades[-1] == {'timestamp': 1609465569.701335, 'amount': Decimal('0.1089'), 'feed': 'FTX_US', 'id': 87074, 'price': Decimal('29404.5'), 'side': SELL, 'symbol': 'BTC-USD'}
        assert len(trades) == 137
