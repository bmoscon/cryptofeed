'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed.defines import BID
from cryptofeed.exchanges.poloniex import Poloniex


poloniex = Poloniex(config='config.yaml')


def teardown_module(module):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    loop.run_until_complete(poloniex.shutdown())


class TestPoloniexRest:
    def test_get_ticker(self):
        ticker = poloniex.ticker_sync('ETH-BTC')
        assert ticker['bid'] > 0


    def test_order_book(self):
        order_book = poloniex.l2_book_sync('ETH-BTC')

        assert len(order_book.book[BID]) > 0


    def test_trade_history(self):
        trade_history = []
        for trade in poloniex.trades_sync('ETH-BTC', start='2021-12-29 00:00:00', end='2021-12-30 00:00:00'):
            trade_history.extend(trade)
        assert len(trade_history) == 4000
        assert trade_history[0]['amount'] == Decimal('0.00918097')
        assert trade_history[0]['symbol'] == 'ETH-BTC'


    def test_trades(self):
        trade_history = []
        for trade in poloniex.trades_sync('BTC-USDT'):
            trade_history.extend(trade)
        assert len(trade_history) == 200
        assert trade_history[0]['amount'] > 0
