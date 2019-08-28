import pandas as pd

from cryptofeed.rest import Rest
from cryptofeed.defines import BUY, SELL


def test_rest_bitmex():
    r = Rest()
    ret = []
    end = pd.Timestamp.now()
    start = end - pd.Timedelta(minutes=2)
    for data in r.bitmex.trades('XBTUSD', start=start, end=end):
        ret.extend(data)

    assert len(ret) > 0


def test_rest_bitfinex():
    expected = {'timestamp': 1483228812.0,
                'pair': 'BTC-USD',
                'id': 25291508,
                'feed': 'BITFINEX',
                'side': SELL,
                'amount': 1.65,
                'price': 966.61}
    r = Rest()
    ret = []
    for data in r.bitfinex.trades('BTC-USD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:13'):
        ret.extend(data)

    assert len(ret) == 1
    assert ret[0] == expected


def test_rest_deribit():
    expected = {'timestamp': 1550062892.378,
                'pair': 'BTC-PERPETUAL',
                'id': 15340745,
                'feed': 'DERIBIT',
                'side': BUY,
                'amount': 700.0,
                'price': 3580.25}
    r = Rest()
    ret = []
    for data in r.deribit.trades('BTC-PERPETUAL', start='2019-02-13 12:59:10', end='2019-02-13 13:01:33'):
        ret.extend(data)
    assert ret[0] == expected
