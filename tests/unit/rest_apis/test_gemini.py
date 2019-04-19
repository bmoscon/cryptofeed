import time

from cryptofeed.rest import Rest

import pytest


public = Rest('config.yaml').Gemini
sandbox = Rest('config.yaml', sandbox=True).Gemini


def test_ticker():
    ticker = public.ticker('BTC-USD')

    assert 'bid' in ticker
    assert 'ask' in ticker


def test_order_book():
    current_order_book = public.l2_book('BTC-USD')

    assert 'bid'in current_order_book
    assert len(current_order_book['bid']) > 0


def test_trade_history():
    trade_history = list(public.trades('BTC-USD'))

    assert len(trade_history) > 0


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_heartbeat():
    result = sandbox.heartbeat()
    assert result['result'] == 'ok'


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_place_order_and_cancel():
    order_resp = sandbox.place_order(
        pair = 'btcusd',
        side = 'buy',
        type='LIMIT',
        amount = '1.0',
        price = '622.13',
        client_order_id='1'
    )
    assert 'order_id' in order_resp
    cancel_resp = sandbox.cancel_order({'order_id': order_resp['order_id']})
    assert 'order_id' in cancel_resp


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_cancel_all_session_orders():
    cancel_all = sandbox.cancel_all_session_orders()
    assert cancel_all['result'] == 'ok'


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_cancel_all_active_orders():
    cancel_all = sandbox.cancel_all_active_orders()
    assert cancel_all['result'] == 'ok'


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_order_status():
    order_resp = sandbox.place_order(
        pair = 'btcusd',
        side = 'buy',
        type='LIMIT',
        amount = '1.0',
        price = '1.13',
        client_order_id='1'
    )
    status = sandbox.order_status({'order_id': order_resp['order_id']})
    sandbox.cancel_all_active_orders()

    assert status['symbol'] == 'btcusd'
    assert status['side'] == 'buy'


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_get_active_orders():
    active = sandbox.get_active_orders()

    assert len(active) == 0


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_get_past_trades():
    trades = sandbox.get_past_trades({'symbol': 'btcusd'})
    assert len(trades) == 0


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_get_notional_volume():
    volume = sandbox.get_notional_volume()

    assert volume['maker_fee_bps'] == 25


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_get_trade_volume():
    volume = sandbox.get_trade_volume()

    assert len(volume) == 1


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_get_available_balances():
    balances = sandbox.get_available_balances()

    assert len(balances) > 0
