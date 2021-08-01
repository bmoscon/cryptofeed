from cryptofeed.defines import ASK, BID
from cryptofeed.exchanges import Bitmex


def test_rest_bitmex():
    ret = []

    for data in Bitmex().trades('BTC-USD-PERP'):
        ret.extend(data)

    assert len(ret) > 0
    assert ret[0]['feed'] == 'BITMEX'
    assert ret[0]['symbol'] == 'BTC-USD-PERP'


def test_ticker():
    ret = Bitmex().ticker('BTC-USD-PERP')
    assert len(ret) > 0
    assert ret[0]['feed'] == 'BITMEX'
    assert ret[0]['symbol'] == 'BTC-USD-PERP'
    assert ret[0]['bid'] > 0
    assert ret[0]['ask'] > 0


def test_book():
    ret = Bitmex().l2_book('BTC-USD-PERP')
    assert BID in ret
    assert ASK in ret
    assert len(ret[BID]) > 0
    assert len(ret[ASK]) > 0