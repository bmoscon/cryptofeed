'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.defines import BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BUY, SELL
from cryptofeed.exchanges import BinanceFutures, BinanceDelivery, Binance
from cryptofeed.types import Candle


b = Binance()
bd = BinanceDelivery()
bf = BinanceFutures()


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(b.shutdown())
    asyncio.get_event_loop().run_until_complete(bf.shutdown())
    asyncio.get_event_loop().run_until_complete(bd.shutdown())


class TestBinanceRest:
    def test_trade(self):
        ret = []
        for data in b.trades_sync('BTC-USDT'):
            ret.extend(data)

        assert len(ret) == 1000
        assert ret[0]['feed'] == BINANCE
        assert ret[0]['symbol'] == 'BTC-USDT'
        assert isinstance(ret[0]['price'], Decimal)
        assert isinstance(ret[0]['amount'], Decimal)
        assert isinstance(ret[0]['timestamp'], float)


    def test_trades(self):
        expected = {'timestamp': 1577836800.594,
                    'symbol': 'BTC-USDT',
                    'id': 202458543,
                    'feed': BINANCE,
                    'side': BUY,
                    'amount': Decimal('0.00150000'),
                    'price': Decimal('7195.24000000')}
        ret = []
        for data in b.trades_sync('BTC-USDT', start='2020-01-01 00:00:00', end='2020-01-01 00:00:01'):
            ret.extend(data)

        assert len(ret) == 3
        assert ret[0] == expected
        assert ret[0]['timestamp'] < ret[-1]['timestamp']
    
    def test_candles(self):
        expected = Candle(
            b.id,
            'BTC-USDT',
            1577836800.0,
            1577836859.999,
            '1m',
            493,
            Decimal('7195.24'),
            Decimal('7186.68'),
            Decimal('7196.25'),
            Decimal('7183.14'),
            Decimal('51.642812'),
            True,
            1577836859.999
        )
        ret = []
        for data in b.candles_sync('BTC-USDT', start='2020-01-01 00:00:00', end='2020-01-01 00:00:59'):
            ret.extend(data)

        assert len(ret) == 1
        assert ret[0] == expected    

    def test_bf_trade(self):
        expected = {'timestamp': 1577836801.481,
                    'symbol': 'BTC-USDT-PERP',
                    'id': 18374167,
                    'feed': BINANCE_FUTURES,
                    'side': BUY,
                    'amount': Decimal('.03'),
                    'price': Decimal('7189.43')}

        ret = []
        for data in bf.trades_sync('BTC-USDT-PERP', start='2020-01-01 00:00:00', end='2020-01-01 0:00:02'):
            ret.extend(data)

        assert len(ret) == 3
        assert ret[0] == expected


    def test_bf_trades(self):
        ret = []
        for data in bf.trades_sync('BTC-USDT-PERP', start='2020-01-01 00:00:00', end='2020-01-01 1:00:00'):
            ret.extend(data)

        assert len(ret) == 2588


    def test_bd_trade(self):
        expected = {'timestamp': 1609459200.567,
                    'symbol': 'BTC-USD-PERP',
                    'id': 8411339,
                    'feed': BINANCE_DELIVERY,
                    'side': SELL,
                    'amount': Decimal('13'),
                    'price': Decimal('28950.4')}

        ret = []
        for data in bd.trades_sync('BTC-USD-PERP', start='2021-01-01 00:00:00', end='2021-01-01 0:00:01'):
            ret.extend(data)

        assert len(ret) == 2
        assert ret[0] == expected


    def test_bd_trades(self):
        ret = []
        for data in bd.trades_sync('BTC-USD-PERP', start='2021-01-01 00:00:00', end='2021-01-01 1:00:00'):
            ret.extend(data)

        assert len(ret) == 6216
