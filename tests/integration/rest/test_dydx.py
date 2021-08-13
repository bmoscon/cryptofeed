from cryptofeed.defines import ASK, BID
from cryptofeed.exchanges import dYdX


def test_trade():
    ret = []
    for data in dYdX().trades_sync('BTC-USD'):
        ret.extend(data)
    assert len(ret) > 1

def test_l2_book():
    ret = dYdX().l2_book_sync('BTC-USD')
    assert BID in ret
    assert ASK in ret
    assert len(ret[BID]) > 0
    assert len(ret[ASK]) > 0
