'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from cryptofeed.defines import ASK, BID, BUY
from decimal import Decimal

from cryptofeed.exchanges.ftx import FTX


f = FTX(config='config.yaml')


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(f.shutdown())


class TestFTXRest:
    def test_funding(self):
        data = f.funding_sync('BTC-USD-PERP')

        assert data[0]['symbol'] == 'BTC-USD-PERP'


    def test_ticker(self):
        ret = f.ticker_sync('BTC-USD-PERP')
        assert ret['feed'] == 'FTX'
        assert ret['symbol'] == 'BTC-USD-PERP'
        assert BID in ret
        assert ASK in ret


    def test_book(self):
        ret = f.l2_book_sync('BTC-USD-PERP')
        assert len(ret.book[BID]) > 1
        assert len(ret.book[ASK]) > 1


    def test_trades(self):
        trades = []

        for t in f.trades_sync('BTC-USD-PERP'):
            trades.extend(t)

        assert len(trades) > 0
        assert trades[0]['feed'] == 'FTX'
        assert trades[0]['symbol'] == 'BTC-USD-PERP'


    def test_trades_history(self):
        trades = []

        for t in f.trades_sync('BTC-USD-PERP', start='2021-01-01 00:00:00', end='2021-01-01 02:00:00'):
            trades.extend(t)
        trades.reverse()

        assert trades[0] == {'timestamp': 1609459200.113814, 'amount': Decimal('0.0001'), 'feed': 'FTX', 'id': 270867343, 'price': Decimal('28961.5'), 'side': BUY, 'symbol': 'BTC-USD-PERP'}
        assert trades[-1] == {'timestamp': 1609466399.091412, 'amount': Decimal('0.0001'), 'feed': 'FTX', 'id': 271124816, 'price': Decimal('29473.0'), 'side': BUY, 'symbol': 'BTC-USD-PERP'}
        assert len(trades) == 38540
