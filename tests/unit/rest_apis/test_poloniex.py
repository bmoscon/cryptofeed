import pytest

from cryptofeed.rest import Rest


poloniex = Rest('config.yaml').Poloniex


def test_get_ticker():
    tickers = poloniex.tickers()

    assert 'BTC_BTS' in tickers
    assert tickers['BTC_BTS']['id'] == 14


def test_past_day_volume():
    past_day = poloniex.past_day_volume()

    assert 'BTC_BCN' in past_day
    assert 'BTC' in past_day['BTC_BCN']
    assert 'BCN' in past_day['BTC_BCN']


def test_order_books():
    order_books = poloniex.order_books({"currencyPair": "BTC_NXT", "depth": 5})

    assert 'asks' in order_books
    assert 'bids' in order_books
    assert len(order_books['asks']) == 5


def test_order_books_1():
    order_books = poloniex.order_books({"currencyPair": "BTC_NXT"})

    assert 'asks' in order_books and 'bids' in order_books


def test_trade_history():
    trade_history = list(next(poloniex.trades('BTC-USDT', start='2018-10-01', end='2018-10-02')))
    assert len(trade_history) > 0
    assert float(trade_history[0]['amount']) > 0


def test_chart_data():
    chart_data = poloniex.chart_data({"currencyPair": "BTC_XMR", "start": 1405699200, "end": 9999999999, "period": 14400})

    assert len(chart_data) > 0
    assert chart_data[0]['volume'] > 0


def test_currencies():
    currencies = poloniex.currencies()

    assert '1CR' in currencies
    assert currencies['1CR']['id'] == 1


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_balances():
    balances = poloniex.balances()

    assert float(balances['UIS']) == 0.0


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_complete_balances():
    complete_balances = poloniex.complete_balances()

    assert float(complete_balances['UIS']['available']) == 0.0


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_deposit_addresses():
    deposit_addresses = poloniex.deposit_addresses()
    if len(deposit_addresses) == 0:
        poloniex.generate_new_address({"currency": "BTC"})

    deposit_addresses = poloniex.deposit_addresses()
    assert len(deposit_addresses) > 0


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_deposit_withdrawals():
    deposit_withdrawals = poloniex.deposit_withdrawals({"start": 1410158341, "end": 1410499372})

    assert 'deposits' in deposit_withdrawals
    assert 'withdrawals' in deposit_withdrawals


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_open_orders():
    poloniex = Rest('config.yaml').Poloniex
    open_orders = poloniex.open_orders()

    assert 'BTC_BCN' in open_orders


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_available_account_balances():
    available_account_balances = poloniex.available_account_balances()

    assert len(available_account_balances) >= 0


@pytest.mark.skipif(poloniex.key_id is None or poloniex.key_secret is None, reason="No api key provided")
def test_tradable_balances():
    tradable_balances = poloniex.tradable_balances()

    assert 'BTC_BTS' in tradable_balances
    assert float(tradable_balances['BTC_BTS']['BTC']) == 0.0
