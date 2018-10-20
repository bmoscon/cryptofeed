import unittest
from cryptofeed.rest import Rest

class TestKraken(unittest.TestCase):
    def test_get_server_time(self):
        kraken = Rest('config.yaml').kraken
        server_time = kraken.get_server_time()
        assert len(server_time['error']) == 0

    def test_get_assets(self):
        kraken = Rest('config.yaml').kraken
        info = kraken.get_asset_info()
        assert 'ADA' in info['result']

    def test_get_assets_payload(self):
        kraken = Rest('config.yaml').kraken
        info = kraken.get_asset_info({"asset": "ada,eos,bch"})
        assert 'ADA' in info['result']

    def test_tradeable_pairs(self):
        kraken = Rest('config.yaml').kraken
        tradeable = kraken.get_tradeable_pairs()
        assert len(tradeable['result']) > 0

    def test_tradeable_pairs_payload(self):
        kraken = Rest('config.yaml').kraken
        tradeable = kraken.get_tradeable_pairs({"info": "leverage", "pair": "adacad"})
        assert 'ADACAD' in tradeable['result']

    def test_get_ohlc_data(self):
        kraken = Rest('config.yaml').kraken
        ohlc = kraken.get_ohlc_data({"pair": "adacad"})
        assert len(ohlc['result']['ADACAD']) > 0

    def test_get_order_book(self):
        kraken = Rest('config.yaml').kraken
        book = kraken.get_order_book({"pair": "adacad"})
        assert len(book['result']['ADACAD']['asks']) > 0

    def test_get_recent_trades(self):
        kraken = Rest('config.yaml').kraken
        trades = kraken.get_recent_trades({"pair": "adacad"})
        assert len(trades['result']['ADACAD']) > 0

    def test_recent_spread_data(self):
        kraken = Rest('config.yaml').kraken
        data = kraken.get_recent_spread_data({"pair": "adacad"})
        assert len(data['result']['ADACAD']) > 0

    def test_get_account_balance(self):
        kraken = Rest('config.yaml').kraken
        balance = kraken.get_account_balance()
        assert balance['error'] == []

    def test_get_open_orders(self):
        kraken = Rest('config.yaml').kraken
        open_orders = kraken.get_open_orders()
        assert open_orders['error'] == []

    def test_get_open_orders_trades(self):
        kraken = Rest('config.yaml').kraken
        open_orders = kraken.get_open_orders({'trades': 'true'})
        assert open_orders['error'] == []

    def test_get_closed_orders(self):
        kraken = Rest('config.yaml').kraken
        closed_orders = kraken.get_closed_orders()
        assert closed_orders['error'] == []

    def test_get_closed_orders_trades(self):
        kraken = Rest('config.yaml').kraken
        closed_orders = kraken.get_closed_orders({'trades': 'true'})
        assert closed_orders['error'] == []

    def test_query_orders_info(self):
        kraken = Rest('config.yaml').kraken
        orders_info = kraken.query_orders_info()
        assert orders_info['error'][0] == 'EGeneral:Invalid arguments'

    def test_get_get_trades_history(self):
        kraken = Rest('config.yaml').kraken
        trades_history = kraken.get_trades_history()
        assert trades_history['error'] == []

    def test_get_get_trades_history_params(self):
        kraken = Rest('config.yaml').kraken
        trades_history = kraken.get_trades_history({'trades': 'true', 'type': 'any position'})
        assert trades_history['error'] == []

    def test_get_query_trades_info(self):
        kraken = Rest('config.yaml').kraken
        trades_info = kraken.query_trades_info({})
        assert trades_info['error'][0] == 'EGeneral:Invalid arguments'


    def test_get_ledgers_info(self):
        kraken = Rest('config.yaml').kraken
        ledgers_info = kraken.get_ledgers_info()
        assert ledgers_info['error'] == []


    def test_get_trade_volume(self):
        kraken = Rest('config.yaml').kraken
        trade_volume = kraken.get_trade_volume()
        assert trade_volume['result']['currency'] == 'ZUSD'


if __name__ == '__main__':
    unittest.main()

kraken = Rest('config.yaml').kraken
kraken.get_account_balance()
