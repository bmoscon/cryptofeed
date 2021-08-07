from decimal import Decimal

import pytest

from cryptofeed.defines import BID, ASK, BUY, LIMIT
from cryptofeed.exchanges import Coinbase


public = Coinbase(config='config.yaml')
sandbox = Coinbase(sandbox=True, config='config.yaml')


def test_ticker():
    ticker = public.ticker_sync('BTC-USD')

    assert BID in ticker
    assert ASK in ticker


def test_order_book():
    current_order_book = public.l2_book_sync('BTC-USD')

    assert BID in current_order_book
    assert len(current_order_book[BID]) > 0


def test_order_book_l3():
    current_order_book = public.l3_book_sync('BTC-USD')

    assert BID in current_order_book
    assert len(current_order_book[BID]) > 0


def test_trade_history():
    trade_history = list(public.trades_sync('BTC-USD'))
    assert len(trade_history) > 0


def test_trade_history_specific_time():
    expected = {'timestamp': 1550062756.744,
                'symbol': 'BTC-USD',
                'id': 59158401,
                'feed': 'COINBASE',
                'side': 'buy',
                'amount': Decimal('0.00514473'),
                'price': Decimal('3580.07')}
    ret = []
    for data in public.trades_sync('BTC-USD', start='2019-02-13 12:59:10', end='2019-02-13 12:59:17'):
        ret.extend(data)

    assert len(ret) == 1
    assert ret[0] == expected


def test_candle_history():
    candle_history = list(public.candles_sync('BTC-USD'))
    assert len(candle_history) > 0


def test_candle_history_specific_time():
    expected = [
        {
            'symbol': 'BTC-USD', 'feed': 'COINBASE',
            'timestamp': 1578733200,
            'low': Decimal('8054.64'),
            'high': Decimal('8122'),
            'open': Decimal('8054.66'),
            'close': Decimal('8109.53'),
            'volume': Decimal('78.91111363')},
        {
            'symbol': 'BTC-USD', 'feed': 'COINBASE',
            'timestamp': 1578736800,
            'low': Decimal('8045.67'),
            'high': Decimal('8110.95'),
            'open': Decimal('8110.95'),
            'close': Decimal('8050.94'),
            'volume': Decimal('71.11516828')
        }
    ]
    s = '2020-01-11 09:00:00'
    e = '2020-01-11 10:00:00'
    granularity = 3600
    candle_history = []
    for entry in public.candles_sync('BTC-USD', start=s, end=e, interval=granularity):
        candle_history.extend(entry)

    assert len(candle_history) == 2
    assert candle_history == expected


@pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
def test_place_order_and_cancel():
    order_resp = sandbox.place_order(
        symbol='BTC-USD',
        side=BUY,
        order_type=LIMIT,
        amount='1.0',
        price='622.13',
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
        symbol='btcusd',
        side='buy',
        type='LIMIT',
        amount='1.0',
        price='1.13',
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
def test_balances():
    balances = sandbox.balances()

    assert len(balances) > 0
