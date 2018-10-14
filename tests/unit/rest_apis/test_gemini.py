import unittest
from cryptofeed.rest import Rest

class TestGemini(unittest.TestCase):

    def test_symbols(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        symbols = gemini.symbols()

        assert len(symbols) == 6

    def test_ticker(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        ticker = gemini.ticker('btcusd')

        assert 'bid' in ticker
        assert 'ask' in ticker

    def test_current_order_book(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        current_order_book = gemini.current_order_book('btcusd')

        assert 'bids'in current_order_book
        assert len(current_order_book['bids']) > 0

    def test_current_order_book_with_params(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        current_order_book = gemini.current_order_book('btcusd', {'limit_bids': 10, 'limit_asks': 10})

        assert 'bids'in current_order_book
        assert len(current_order_book['bids']) == 10
        assert len(current_order_book['asks']) == 10


    def test_trade_history(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        trade_history = gemini.trade_history('btcusd')

        assert len(trade_history) > 0

    def test_trade_history_with_parameters(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        trade_history = gemini.trade_history(
            'btcusd',
            {'since': 1539224800, 'limit_trades': 10, 'include_breaks': 'true'}
        )

        assert len(trade_history) == 10

    def test_current_auction(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        current_auction = gemini.current_auction('btcusd')

        assert 'last_auction_price' in current_auction

    def test_auction_history(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        auction_history = gemini.auction_history('btcusd')

        assert len(auction_history) > 0

    def test_auction_history_with_parameters(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        auction_history = gemini.auction_history(
            'btcusd',
            {'since': 1539201420000, 'limit_auction_results': 5, 'include_indicative': 'true'}
        )

        assert len(auction_history) == 5

    def test_heartbeat(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        result = gemini.heartbeat()
        assert result['result'] == 'ok'


    def test_new_order_and_cancel(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        order_resp = gemini.new_order({
            "client_order_id": "1",
            "symbol": "BTCUSD",
            "amount": "1.0",
            "price": "622.13",
            "side": "buy",
            "type": "exchange limit"
        })
        assert 'order_id' in order_resp
        cancel_resp = gemini.cancel_order({'order_id': order_resp['order_id']})
        assert 'order_id' in cancel_resp


    def test_cancel_all_session_orders(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        cancel_all = gemini.cancel_all_session_orders()
        assert cancel_all['result'] == 'ok'


    def test_cancel_all_active_orders(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        cancel_all = gemini.cancel_all_active_orders()
        assert cancel_all['result'] == 'ok'

    def test_order_status(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        order_resp = gemini.new_order({
            "client_order_id": "1",
            "symbol": "BTCUSD",
            "amount": "1.0",
            "price": "1.13",
            "side": "buy",
            "type": "exchange limit"
        })
        status = gemini.order_status({'order_id': order_resp['order_id']})
        gemini.cancel_all_active_orders()

        assert status['symbol'] == 'btcusd'
        assert status['side'] == 'buy'


    def test_get_active_orders(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        active = gemini.get_active_orders()

        assert len(active) == 0


    def test_get_past_trades(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        trades = gemini.get_past_trades({'symbol': 'btcusd'})
        assert len(trades) == 0

    def test_get_notional_volume(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        volume = gemini.get_notional_volume()

        assert volume['maker_fee_bps'] == 25

    def test_get_trade_volume(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        volume = gemini.get_trade_volume()

        assert len(volume) == 1

    def test_get_available_balances(self):
        gemini = Rest('config.yaml', sandbox=True).Gemini
        balances = gemini.get_available_balances()

        assert len(balances) > 0


if __name__ == '__main__':
    unittest.main()
