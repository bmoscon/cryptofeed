from cryptofeed.rest import Rest


def test_rest_bitmex():
    expected = {'timestamp': '2017-01-01T00:00:36.806Z', 
                'pair': 'XBTUSD',
                'id': 'e4db2886-ae1d-4191-c516-566fb703365c',
                'feed': 'BITMEX',
                'side': 'Buy',
                'amount': 500,
                'price': 968.49}
                
    r = Rest()
    ret = []
    for data in r.bitmex.trades('XBTUSD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:37'):
        ret.extend(data)
    
    assert len(ret) == 4
    assert ret[0] == expected


def test_rest_bitfinex():
    expected = {'timestamp': '2017-01-01T00:00:12.000000Z',
                'pair': 'BTC-USD',
                'id': 25291508,
                'feed': 'BITFINEX',
                'side': 'Sell',
                'amount': 1.65,
                'price': 966.61}
    r = Rest()
    ret = []
    for data in r.bitfinex.trades('BTC-USD', start='2017-01-01 00:00:00', end='2017-01-01 0:00:13'):
        ret.extend(data)
    
    assert len(ret) == 1
    assert ret[0] == expected
