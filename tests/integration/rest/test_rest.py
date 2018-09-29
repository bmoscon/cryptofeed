from cryptofeed.rest import Rest


def test_rest_bitmex():
    expected = {'timestamp': '2018-09-29T00:00:09.939Z',
                'pair': 'XBTUSD',
                'id': '58db4844-82b2-40e9-de90-c4d1672af7cc',
                'feed': 'BITMEX',
                'side': 'Sell',
                'amount': 265,
                'price': 6620}
                
    r = Rest()
    ret = []
    for data in r.bitmex.trades('XBTUSD', start='2018-09-29 00:00:09.939', end='2018-09-29 00:00:10'):
        ret.extend(data)
    
    assert len(ret) == 1
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
