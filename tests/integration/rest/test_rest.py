from datetime import datetime as dt, timedelta

from cryptofeed.defines import SELL, BITFINEX
from cryptofeed.exchanges import Bitmex, Bitfinex, Deribit, FTX


def test_rest_bitmex():
    ret = []
    end = dt.now()
    start = end - timedelta(minutes=2)
    for data in Bitmex().trades('BTC-USD-PERP', start=start, end=end):
        ret.extend(data)

    assert len(ret) > 0


def test_rest_bitfinex():
    expected = {'timestamp': 1483228812.0,
                'symbol': 'BTC-USD',
                'id': 25291508,
                'feed': BITFINEX,
                'side': SELL,
                'amount': 1.65,
                'price': 966.61}

    ret = []
    for data in Bitfinex().trades('BTC-USD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:13'):
        ret.extend(data)

    assert len(ret) == 1
    assert ret[0] == expected


def test_rest_deribit():
    ret = []
    for data in Deribit().trades('BTC-USD-PERP'):
        ret.extend(data)
    assert len(ret) > 1
