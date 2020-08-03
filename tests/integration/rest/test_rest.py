import pandas as pd

from cryptofeed.defines import BUY, SELL
from cryptofeed.rest import Rest


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


def test_rest_ftx():
    expected = {'timestamp': 1591992000.0,
                'pair': 'BTC-PERP',
                'feed': 'FTX',
                'rate': -9e-06}

    r = Rest()
    ret = []
    data = r.ftx.funding('BTC-PERP', start_date='2020-06-10 12:59:10', end_date='2020-06-13 13:01:33')
    ret.extend(data)
    try:
        assert ret[0] == expected
    except AssertionError as ex:
        print(f'test_rest_ftx failed: {ex!r}')
        print('Please check the start_date, because FTX only saves 4 months worth of funding data')
