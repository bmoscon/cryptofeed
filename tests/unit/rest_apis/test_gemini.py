import unittest
from cryptofeed.rest import Rest

class TestGemini(unittest.TestCase):

    def test_symbols(self):
        gemini = Rest('config.yaml').Gemini
        symbols = gemini.symbols()

        assert len(symbols) == 6

    def test_ticker(self):
        gemini = Rest('config.yaml').Gemini
        ticker = gemini.ticker('btcusd')

        assert 'bid' in ticker
        assert 'ask' in ticker

    def test_current_order_book(self):
        gemini = Rest('config.yaml').Gemini
        current_order_book = gemini.current_order_book('btcusd')

        assert 'bids'in current_order_book
        assert len(current_order_book['bids']) > 0

    def test_current_order_book_with_params(self):
        gemini = Rest('config.yaml').Gemini
        current_order_book = gemini.current_order_book('btcusd', {'limit_bids': 10, 'limit_asks': 10})

        assert 'bids'in current_order_book
        assert len(current_order_book['bids']) == 10
        assert len(current_order_book['asks']) == 10


    def test_trade_history(self):
        gemini = Rest('config.yaml').Gemini
        trade_history = gemini.trade_history('btcusd')

        assert len(trade_history) > 0

    def test_trade_history_with_parameters(self):
        gemini = Rest('config.yaml').Gemini
        trade_history = gemini.trade_history(
            'btcusd',
            {'since': 1539224800, 'limit_trades': 10, 'include_breaks': 'true'}
        )

        assert len(trade_history) == 10

    def test_current_auction(self):
        gemini = Rest('config.yaml').Gemini
        current_auction = gemini.current_auction('btcusd')

        assert 'last_auction_price' in current_auction

    def test_auction_history(self):
        gemini = Rest('config.yaml').Gemini
        auction_history = gemini.auction_history('btcusd')

        assert len(auction_history) > 0

    def test_auction_history_with_parameters(self):
        gemini = Rest('config.yaml').Gemini
        auction_history = gemini.auction_history(
            'btcusd',
            {'since': 1539201420000, 'limit_auction_results': 5, 'include_indicative': 'true'}
        )

        assert len(auction_history) == 5


if __name__ == '__main__':
    unittest.main()
