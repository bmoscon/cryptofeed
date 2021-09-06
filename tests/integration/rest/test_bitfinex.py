'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.defines import ASK, BID, BUY, SELL, BITFINEX
from cryptofeed.exchanges import Bitfinex


b = Bitfinex()


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(b.shutdown())


class TestBitfinexRest:
    def test_trade(self):
        expected = {'timestamp': 1483228812.0,
                    'symbol': 'BTC-USD',
                    'id': 25291508,
                    'feed': BITFINEX,
                    'side': SELL,
                    'amount': Decimal('1.65'),
                    'price': Decimal('966.61')}

        ret = []
        for data in b.trades_sync('BTC-USD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:13'):
            ret.extend(data)

        assert len(ret) == 1
        assert ret[0] == expected


    def test_trades(self):
        ret = []
        for data in b.trades_sync('BTC-USD', start='2019-01-01 00:00:00', end='2019-01-01 8:00:13'):
            ret.extend(data)

        assert len(ret) == 8320
        assert ret[0] == {'symbol': 'BTC-USD', 'feed': 'BITFINEX', 'side': BUY, 'amount': Decimal('0.27273351'), 'price': Decimal('3834.7'), 'id': 329252035, 'timestamp': 1546300800.0}
        assert ret[-1] == {'symbol': 'BTC-USD', 'feed': 'BITFINEX', 'side': BUY, 'amount': Decimal('0.01631427'), 'id': 329299342, 'price': Decimal(3850), 'timestamp': 1546329604.0}


    def test_ticker(self):
        ret = b.ticker_sync('BTC-USD')
        assert isinstance(ret, dict)
        assert ret['feed'] == 'BITFINEX'
        assert ret['symbol'] == 'BTC-USD'
        assert ret['bid'] > 0
        assert ret['ask'] > 0


    def test_l2_book(self):
        ret = b.l2_book_sync('BTC-USD')
        assert len(ret.book[BID]) > 0
        assert len(ret.book[ASK]) > 0


    def test_l3_book(self):
        ret = b.l3_book_sync('BTC-USD')
        assert len(ret.book[BID]) > 0
        assert len(ret.book[ASK]) > 0
