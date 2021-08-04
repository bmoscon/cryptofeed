from decimal import Decimal

from cryptofeed.defines import ASK, BID, BUY, SELL, BITFINEX
from cryptofeed.exchanges import Bitfinex


def test_trade():
    expected = {'timestamp': 1483228812.0,
                'symbol': 'BTC-USD',
                'id': 25291508,
                'feed': BITFINEX,
                'side': SELL,
                'amount': Decimal('1.65'),
                'price': Decimal('966.61')}

    ret = []
    for data in Bitfinex().trades('BTC-USD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:13'):
        ret.extend(data)

    assert len(ret) == 1
    assert ret[0] == expected


def test_trades():
    ret = []
    for data in Bitfinex().trades('BTC-USD', start='2019-01-01 00:00:00', end='2019-01-01 8:00:13'):
        ret.extend(data)

    assert len(ret) == 8320
    assert ret[0] == {'symbol': 'BTC-USD', 'feed': 'BITFINEX', 'side': BUY, 'amount': Decimal('0.27273351'), 'price': Decimal('3834.7'), 'id': 329252035, 'timestamp': 1546300800.0}
    assert ret[-1] == {'symbol': 'BTC-USD', 'feed': 'BITFINEX', 'side': BUY, 'amount': Decimal('0.01631427'), 'id': 329299342, 'price': Decimal(3850), 'timestamp': 1546329604.0}


def test_ticker():
    ret = Bitfinex().ticker('BTC-USD')
    assert isinstance(ret, dict)
    assert ret['feed'] == 'BITFINEX'
    assert ret['symbol'] == 'BTC-USD'
    assert ret['bid'] > 0
    assert ret['ask'] > 0


def test_funding():
    f = []
    for funding in Bitfinex().funding('BTC'):
        f.extend(funding)
    assert len(f) > 0


def test_l2_book():
    ret = Bitfinex().l2_book('BTC-USD')
    assert BID in ret
    assert ASK in ret
    assert len(ret[BID]) > 0
    assert len(ret[ASK]) > 0

def test_l3_book():
    ret = Bitfinex().l3_book('BTC-USD')
    assert BID in ret
    assert ASK in ret
    assert len(ret[BID]) > 0
    assert len(ret[ASK]) > 0
