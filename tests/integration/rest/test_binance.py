from decimal import Decimal

from cryptofeed.defines import BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BUY, SELL
from cryptofeed.exchanges import BinanceFutures, BinanceDelivery, Binance


def test_trade():
    ret = []
    for data in Binance().trades_sync('BTC-USDT'):
        ret.extend(data)

    assert len(ret) == 1000
    assert ret[0]['feed'] == BINANCE
    assert ret[0]['symbol'] == 'BTC-USDT'
    assert isinstance(ret[0]['price'], Decimal)
    assert isinstance(ret[0]['amount'], Decimal)
    assert isinstance(ret[0]['timestamp'], float)


def test_trades():
    expected = {'timestamp': 1577836800.594,
                'symbol': 'BTC-USDT',
                'id': 202458543,
                'feed': BINANCE,
                'side': BUY,
                'amount': Decimal('0.00150000'),
                'price': Decimal('7195.24000000')}
    ret = []
    for data in Binance().trades_sync('BTC-USDT', start='2020-01-01 00:00:00', end='2020-01-01 00:00:01'):
        ret.extend(data)

    assert len(ret) == 3
    assert ret[0] == expected
    assert ret[0]['timestamp'] < ret[-1]['timestamp']


def test_bf_trade():
    expected = {'timestamp': 1577836801.481,
                'symbol': 'BTC-USDT-PERP',
                'id': 18374167,
                'feed': BINANCE_FUTURES,
                'side': BUY,
                'amount': Decimal('.03'),
                'price': Decimal('7189.43')}

    ret = []
    for data in BinanceFutures().trades_sync('BTC-USDT-PERP', start='2020-01-01 00:00:00', end='2020-01-01 0:00:02'):
        ret.extend(data)

    assert len(ret) == 3
    assert ret[0] == expected


def test_bf_trades():
    ret = []
    for data in BinanceFutures().trades_sync('BTC-USDT-PERP', start='2020-01-01 00:00:00', end='2020-01-01 1:00:00'):
        ret.extend(data)

    assert len(ret) == 2588


def test_bd_trade():
    expected = {'timestamp': 1609459200.567,
                'symbol': 'BTC-USD-PERP',
                'id': 8411339,
                'feed': BINANCE_DELIVERY,
                'side': SELL,
                'amount': Decimal('13'),
                'price': Decimal('28950.4')}

    ret = []
    for data in BinanceDelivery().trades_sync('BTC-USD-PERP', start='2021-01-01 00:00:00', end='2021-01-01 0:00:01'):
        ret.extend(data)

    assert len(ret) == 2
    assert ret[0] == expected


def test_bd_trades():
    ret = []
    for data in BinanceDelivery().trades_sync('BTC-USD-PERP', start='2021-01-01 00:00:00', end='2021-01-01 1:00:00'):
        ret.extend(data)

    assert len(ret) == 6216
