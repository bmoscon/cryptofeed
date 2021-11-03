'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import pytest

from cryptofeed.defines import ASK, BID, KRAKEN
from cryptofeed.exchanges.kraken import Kraken


kraken = Kraken(config='config.yaml')


def teardown_module(module):
    asyncio.get_event_loop().run_until_complete(kraken.shutdown())


class TestKrakenRest:
    def test_get_order_book(self):
        book = kraken.l2_book_sync('BTC-USD')
        assert len(book.book[BID]) > 0


    def test_get_recent_trades(self):
        trades = list(kraken.trades_sync('BTC-USD'))[0]
        assert len(trades) > 0
        assert trades[0]['feed'] == KRAKEN
        assert trades[0]['symbol'] == 'BTC-USD'


    def test_ticker(self):
        t = kraken.ticker_sync('BTC-USD')
        assert t['symbol'] == 'BTC-USD'
        assert t['feed'] == KRAKEN
        assert BID in t
        assert ASK in t


    def test_historical_trades(self):
        trades = []
        for t in kraken.trades_sync('BTC-USD', start='2021-01-01 00:00:01', end='2021-01-01 00:00:05'):
            trades.extend(t)
        assert len(trades) == 13

        trades = []
        for t in kraken.trades_sync('BTC-USD', start='2021-01-01 00:00:01', end='2021-01-01 01:00:00'):
            trades.extend(t)
        assert len(trades) == 2074


    @pytest.mark.skipif(not kraken.key_id or not kraken.key_secret, reason="No api key provided")
    def test_trade_history(self):
        trade_history = kraken.trade_history_sync()
        # for trade in trade_history:
        #     for k, v in trade.items():
        #         print(f"{k} => {v}")
        assert len(trade_history) != 0

    @pytest.mark.skipif(not kraken.key_id or not kraken.key_secret, reason="No api key provided")
    def test_ledger(self):
        ledger = kraken.ledger_sync()
        # for trade in trade_history:
        #     for k, v in trade.items():
        #         print(f"{k} => {v}")
        assert len(ledger) != 0