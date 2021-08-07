from cryptofeed.defines import ASK, BID
from datetime import datetime as dt, timedelta
from decimal import Decimal

from cryptofeed.exchanges import Deribit


def test_trade():
    ret = []
    for data in Deribit().trades_sync('BTC-USD-PERP'):
        ret.extend(data)
    assert len(ret) > 1


def test_trades():
    ret = []
    start = dt.now() - timedelta(days=5)
    end = dt.now() - timedelta(days=4, hours=19)

    for data in Deribit().trades_sync('BTC-USD-PERP', start=start, end=end):
        ret.extend(data)
    assert len(ret) > 1000
    assert ret[0]['symbol'] == 'BTC-USD-PERP'
    assert isinstance(ret[0]['price'], Decimal)
    assert isinstance(ret[0]['amount'], Decimal)


def test_l2_book():
    ret = Deribit().l2_book_sync('BTC-USD-PERP')
    assert BID in ret
    assert ASK in ret
    assert len(ret[BID]) > 0
    assert len(ret[ASK]) > 0