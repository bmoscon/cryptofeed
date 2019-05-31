from cryptofeed.rest import Rest
from cryptofeed.defines import BUY, SELL


def test_rest_bitmex():
    r = Rest()
    ret = []
    for data in r.bitmex.trades('XBTUSD', start='2019-05-01 00:00:09', end='2019-05-01 00:00:15'):
        ret.extend(data)

    assert len(ret) == 2


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
