import pytest

from cryptofeed.defines import BID, ASK
from cryptofeed.rest import Rest


poloniex = Rest().Poloniex


def test_get_ticker():
    ticker = poloniex.ticker('ETH-BTC')
    assert ticker['bid'] > 0


def test_order_book():
    order_book = poloniex.l2_book('ETH-BTC')

    assert BID in order_book
    assert ASK in order_book
    assert len(order_book[BID]) > 0


def test_trade_history():
    trade_history = list(next(poloniex.trades('ETH-BTC', start='2020-12-30', end='2020-12-31')))
    assert len(trade_history) > 0
    assert float(trade_history[0]['amount']) > 0


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_balances():
    balances = poloniex.balances()

    assert float(balances['UIS']) == 0.0


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_complete_balances():
    complete_balances = poloniex.complete_balances()

    assert float(complete_balances['UIS']['available']) == 0.0


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_deposit_addresses():
    deposit_addresses = poloniex.deposit_addresses()
    if len(deposit_addresses) == 0:
        poloniex.generate_new_address({"currency": "BTC"})

    deposit_addresses = poloniex.deposit_addresses()
    assert len(deposit_addresses) > 0


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_deposit_withdrawals():
    deposit_withdrawals = poloniex.deposit_withdrawals({"start": 1410158341, "end": 1410499372})

    assert 'deposits' in deposit_withdrawals
    assert 'withdrawals' in deposit_withdrawals


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_open_orders():
    poloniex = Rest().Poloniex
    open_orders = poloniex.open_orders()

    assert 'BTC_BCN' in open_orders


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_available_account_balances():
    available_account_balances = poloniex.available_account_balances()

    assert len(available_account_balances) >= 0


@pytest.mark.skipif(not poloniex.config.key_id or not poloniex.config.key_secret, reason="No api key provided")
def test_tradable_balances():
    tradable_balances = poloniex.tradable_balances()

    assert 'BTC_BTS' in tradable_balances
    assert float(tradable_balances['BTC_BTS']['BTC']) == 0.0
