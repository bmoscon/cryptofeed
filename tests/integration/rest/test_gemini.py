import pytest

from cryptofeed.defines import BID, ASK, LIMIT, BUY, CANCELLED
from cryptofeed.exchanges import Gemini


public = Gemini(config='config.yaml')
sandbox = Gemini(sandbox=True, config='config.yaml')


def test_ticker():
    ticker = public.ticker_sync('BTC-USD')

    assert BID in ticker
    assert ASK in ticker


def test_order_book():
    current_order_book = public.l2_book_sync('BTC-USD')

    assert BID in current_order_book
    assert len(current_order_book[BID]) > 0


def test_trade_history():
    trade_history = list(public.trades_sync('BTC-USD'))
    assert len(trade_history) > 0


@pytest.mark.skipif(not sandbox.key_id or not sandbox.key_secret, reason="No api key provided")
def test_place_order_and_cancel():
    order_resp = sandbox.place_order_sync(
        symbol='BTC-USD',
        side=BUY,
        order_type=LIMIT,
        amount='1.0',
        price='622.13',
        client_order_id='1'
    )

    assert 'order_id' in order_resp
    assert order_resp['order_status'] != CANCELLED
    cancel_resp = sandbox.cancel_order_sync(order_resp['order_id'])
    assert cancel_resp['order_status'] == CANCELLED


@pytest.mark.skipif(not sandbox.key_id or not sandbox.key_secret, reason="No api key provided")
def test_order_status():
    order_resp = sandbox.place_order_sync(
        symbol='BTC-USD',
        side=BUY,
        order_type=LIMIT,
        amount='1.0',
        price='1.13',
        client_order_id='1'
    )
    status = sandbox.order_status_sync(order_resp['order_id'])
    sandbox.cancel_order_sync(order_resp['order_id'])

    assert status['symbol'] == 'BTC-USD'
    assert status['side'] == BUY


@pytest.mark.skipif(not sandbox.key_id or not sandbox.key_secret, reason="No api key provided")
def test_get_orders():
    orders = sandbox.orders_sync()
    for order in orders:
        sandbox.cancel_order_sync(order['order_id'])

    orders = sandbox.orders_sync()
    assert len(orders) == 0


@pytest.mark.skipif(not sandbox.key_id or not sandbox.key_secret, reason="No api key provided")
def test_balances():
    balances = sandbox.balances_sync()

    assert len(balances) > 0
