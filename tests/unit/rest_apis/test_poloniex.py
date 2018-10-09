import unittest
from cryptofeed.rest import Rest


class TestPoloniex(unittest.TestCase):

    def test_get_ticker(self):
        poloniex = Rest('config.yaml').Poloniex
        tickers = poloniex.tickers()

        assert 'BTC_BTS' in tickers
        assert tickers['BTC_BTS']['id'] == 14

    def test_past_day_volume(self):
        poloniex = Rest('config.yaml').Poloniex
        past_day = poloniex.past_day_volume()

        assert 'BTC_BCN' in past_day
        assert 'BTC' in past_day['BTC_BCN']
        assert 'BCN' in past_day['BTC_BCN']

    def test_order_books(self):
        poloniex = Rest('config.yaml').Poloniex
        order_books = poloniex.order_books({"currencyPair": "BTC_NXT", "depth": 5})

        assert 'asks' in order_books
        assert 'bids' in order_books
        assert len(order_books['asks']) == 5

    def test_order_books_1(self):
        poloniex = Rest('config.yaml').Poloniex
        order_books = poloniex.order_books({"currencyPair": "BTC_NXT"})

        assert 'asks' in order_books and 'bids' in order_books

    def test_trade_history(self):
        poloniex = Rest('config.yaml').Poloniex
        trade_history = poloniex.all_trade_history({"currencyPair": "BTC_NXT", "start": 1410158341, "end": 1410499372})
        assert len(trade_history) > 0
        assert float(trade_history[0]['amount']) > 0

    def test_chart_data(self):
        poloniex = Rest('config.yaml').Poloniex
        chart_data = poloniex.chart_data({"currencyPair": "BTC_XMR", "start": 1405699200, "end": 9999999999, "period": 14400})

        assert len(chart_data) > 0
        assert chart_data[0]['volume'] > 0

    def test_currencies(self):
        poloniex = Rest('config.yaml').Poloniex
        currencies = poloniex.currencies()

        assert '1CR' in currencies
        assert currencies['1CR']['id'] == 1

    def test_balances(self):
        poloniex = Rest('config.yaml').Poloniex
        balances = poloniex.balances()

        assert float(balances['UIS']) == 0.0

    def test_complete_balances(self):
        poloniex = Rest('config.yaml').Poloniex
        complete_balances = poloniex.complete_balances()

        assert float(complete_balances['UIS']['available']) == 0.0


    def test_deposit_addresses(self):
        poloniex = Rest('config.yaml').Poloniex
        deposit_addresses = poloniex.deposit_addresses()
        if len(deposit_addresses) == 0:
            poloniex.generate_new_address({"currency": "BTC"})

        deposit_addresses = poloniex.deposit_addresses()
        assert len(deposit_addresses) > 0

    def test_deposit_withdrawals(self):
        poloniex = Rest('config.yaml').Poloniex
        deposit_withdrawals = poloniex.deposit_withdrawals({"start": 1410158341, "end": 1410499372})

        assert 'deposits' in deposit_withdrawals
        assert 'withdrawals' in deposit_withdrawals

    def test_open_orders(self):
        poloniex = Rest('config.yaml').Poloniex
        open_orders = poloniex.open_orders()

        assert 'BTC_AMP' in open_orders

    def test_trade_history(self):
        poloniex = Rest('config.yaml').Poloniex
        trade_history = poloniex.trade_history()

        assert len(trade_history) >= 0

    def test_available_account_balances(self):
        poloniex = Rest('config.yaml').Poloniex
        available_account_balances = poloniex.available_account_balances()

        assert len(available_account_balances) >= 0

    def test_tradable_balances(self):
        poloniex = Rest('config.yaml').Poloniex
        tradable_balances = poloniex.tradable_balances()

        assert 'BTC_BTS' in tradable_balances
        assert float(tradable_balances['BTC_BTS']['BTC']) == 0.0

if __name__ == '__main__':
    unittest.main()
