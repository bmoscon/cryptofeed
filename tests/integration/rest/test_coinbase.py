'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

import pytest

from cryptofeed.defines import BID, ASK, BUY, LIMIT
from cryptofeed.exchanges import Coinbase
from cryptofeed.types import Candle


public = Coinbase(config='config.yaml')
sandbox = Coinbase(sandbox=True, config='config.yaml')


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(public.shutdown())
    asyncio.get_event_loop().run_until_complete(sandbox.shutdown())


class TestCoinbaseRest:
    def test_ticker(self):
        ticker = public.ticker_sync('BTC-USD')

        assert BID in ticker
        assert ASK in ticker


    def test_order_book(self):
        current_order_book = public.l2_book_sync('BTC-USD')
        assert len(current_order_book.book.bids) > 0


    def test_order_book_l3(self):
        current_order_book = public.l3_book_sync('BTC-USD')
        assert len(current_order_book.book.bids) > 0


    def test_trade_history(self):
        trade_history = list(public.trades_sync('BTC-USD'))
        assert len(trade_history) > 0


    def test_trade_history_specific_time(self):
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


    def test_candle_history(self):
        candle_history = list(public.candles_sync('BTC-USD'))
        assert len(candle_history) > 0


    def test_candle_history_specific_time(self):
        expected = [
            Candle(
                Coinbase.id,
                'BTC-USD',
                1578733200,
                1578733200 + 3600,
                '1h',
                None,
                Decimal('8054.66'),
                Decimal('8109.53'),
                Decimal('8122'),
                Decimal('8054.64'),
                Decimal('78.91111363'),
                True,
                1578733200
            ),
            Candle(
                Coinbase.id,
                'BTC-USD',
                1578736800,
                1578736800 + 3600,
                '1h',
                None,
                Decimal('8110.95'),
                Decimal('8050.94'),
                Decimal('8110.95'),
                Decimal('8045.67'),
                Decimal('71.11516828'),
                True,
                1578736800
            )
        ]
        s = '2020-01-11 09:00:00'
        e = '2020-01-11 10:00:00'
        candle_history = []
        for entry in public.candles_sync('BTC-USD', start=s, end=e, interval='1h'):
            candle_history.extend(entry)

        assert len(candle_history) == 2
        assert candle_history == expected


    @pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
    def test_place_order_and_cancel(self):
        order_resp = sandbox.place_order_sync(
            symbol='BTC-USD',
            side=BUY,
            order_type=LIMIT,
            amount='1.0',
            price='622.13',
            client_order_id='1'
        )
        assert 'order_id' in order_resp
        cancel_resp = sandbox.cancel_order_sync({'order_id': order_resp['order_id']})
        assert 'order_id' in cancel_resp


    @pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
    def test_order_status(self):
        order_resp = sandbox.place_order_sync(
            symbol='btcusd',
            side='buy',
            type='LIMIT',
            amount='1.0',
            price='1.13',
            client_order_id='1'
        )
        status = sandbox.order_status({'order_id': order_resp['order_id']})

        assert status['symbol'] == 'btcusd'
        assert status['side'] == 'buy'
        sandbox.cancel_order_sync({'order_id': order_resp['order_id']})


    @pytest.mark.skipif(sandbox.key_id is None or sandbox.key_secret is None, reason="No api key provided")
    def test_balances(self):
        balances = sandbox.balances_sync()

        assert len(balances) > 0
