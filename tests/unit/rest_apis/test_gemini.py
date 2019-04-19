import time

from cryptofeed.rest import Rest

import pytest


public = Rest('config.yaml').Gemini
sandbox = Rest('config.yaml', sandbox=True).Gemini


def test_symbols():
    symbols = public.symbols()

    assert len(symbols) >= 10


def test_ticker():
    ticker = public.ticker('btcusd')

    assert 'bid' in ticker
    assert 'ask' in ticker


def test_current_order_book():
    current_order_book = public.current_order_book('btcusd')

    assert 'bids'in current_order_book
    assert len(current_order_book['bids']) > 0


def test_current_order_book_with_params():
    current_order_book = public.current_order_book('btcusd', {'limit_bids': 10, 'limit_asks': 10})

    assert 'bids'in current_order_book
    assert len(current_order_book['bids']) == 10
    assert len(current_order_book['asks']) == 10


def test_trade_history():
    trade_history = public.trade_history('btcusd')

    assert len(trade_history) > 0


def test_trade_history_with_parameters():
    since = int(time.time() - 86400)
    trade_history = public.trade_history('btcusd', {'since': since,
                                                    'limit_trades': 10,
                                                    'include_breaks': 'true'})

    assert len(trade_history) == 10


def test_current_auction():
    current_auction = public.current_auction('btcusd')

    assert 'next_auction_ms' in current_auction


def test_auction_history():
    auction_history = public.auction_history('btcusd')

    assert len(auction_history) > 0


def test_auction_history_with_parameters():
    since = int(time.time() - 86400)
    auction_history = public.auction_history(
        'btcusd',
        {'since': since, 'limit_auction_results': 1, 'include_indicative': 'true'}
    )

    assert len(auction_history) > 0


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
