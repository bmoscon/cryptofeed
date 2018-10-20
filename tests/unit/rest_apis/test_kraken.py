import pytest
from cryptofeed.rest import Rest


kraken = Rest('config.yaml').kraken


def test_get_server_time():
    server_time = kraken.get_server_time()
    assert len(server_time['error']) == 0


def test_get_assets():
    info = kraken.get_asset_info()
    assert 'ADA' in info['result']


def test_get_assets_payload():
    info = kraken.get_asset_info({"asset": "ada,eos,bch"})
    assert 'ADA' in info['result']


def test_tradeable_pairs():
    tradeable = kraken.get_tradeable_pairs()
    assert len(tradeable['result']) > 0


def test_tradeable_pairs_payload():
    tradeable = kraken.get_tradeable_pairs({"info": "leverage", "pair": "adacad"})
    assert 'ADACAD' in tradeable['result']


def test_get_ohlc_data():
    ohlc = kraken.get_ohlc_data({"pair": "adacad"})
    assert len(ohlc['result']['ADACAD']) > 0


def test_get_order_book():
    book = kraken.get_order_book({"pair": "adacad"})
    assert len(book['result']['ADACAD']['asks']) > 0


def test_get_recent_trades():
    trades = kraken.get_recent_trades({"pair": "adacad"})
    assert len(trades['result']['ADACAD']) > 0


def test_recent_spread_data():
    data = kraken.get_recent_spread_data({"pair": "adacad"})
    assert len(data['result']['ADACAD']) > 0


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
