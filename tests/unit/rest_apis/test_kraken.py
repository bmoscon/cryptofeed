import pytest
from cryptofeed.rest import Rest
from cryptofeed.defines import BID


kraken = Rest('config.yaml').kraken


def test_get_order_book():
    book = kraken.l2_book('BTC-USD')
    assert len(book[BID]) > 0


def test_get_recent_trades():
    trades = list(kraken.trades('BTC-USD'))
    assert len(trades) > 0


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_account_balance():
    balance = kraken.get_account_balance()
    assert balance['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_open_orders():
    open_orders = kraken.get_open_orders()
    assert open_orders['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_open_orders_trades():
    open_orders = kraken.get_open_orders({'trades': 'true'})
    assert open_orders['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_closed_orders():
    closed_orders = kraken.get_closed_orders()
    assert closed_orders['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_closed_orders_trades():
    closed_orders = kraken.get_closed_orders({'trades': 'true'})
    assert closed_orders['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_query_orders_info():
    orders_info = kraken.query_orders_info()
    assert orders_info['error'][0] == 'EGeneral:Invalid arguments'


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_get_trades_history():
    trades_history = kraken.get_trades_history()
    assert trades_history['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_get_trades_history_params():
    trades_history = kraken.get_trades_history({'trades': 'true', 'type': 'any position'})
    assert trades_history['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_query_trades_info():
    trades_info = kraken.query_trades_info({})
    assert trades_info['error'][0] == 'EGeneral:Invalid arguments'


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_ledgers_info():
    ledgers_info = kraken.get_ledgers_info()
    assert ledgers_info['error'] == []


@pytest.mark.skipif(kraken.key_id is None or kraken.key_secret is None, reason="No api key provided")
def test_get_trade_volume():
    trade_volume = kraken.get_trade_volume()
    assert trade_volume['result']['currency'] == 'ZUSD'
