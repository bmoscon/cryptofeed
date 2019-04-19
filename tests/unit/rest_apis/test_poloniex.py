import pytest

from cryptofeed.rest import Rest
from cryptofeed.defines import BID, ASK


poloniex = Rest('config.yaml').Poloniex


def test_get_ticker():
    ticker = poloniex.ticker('BTC-USDT')
    assert ticker['bid'] > 0


def test_order_book():
    order_book = poloniex.l2_book('BTC-USDT')

    assert BID in order_book
    assert ASK in order_book
    assert len(order_book[BID]) > 0


def test_trade_history():
    trade_history = list(next(poloniex.trades('BTC-USDT', start='2018-10-01', end='2018-10-02')))
    assert len(trade_history) > 0
    assert float(trade_history[0]['amount']) > 0


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
