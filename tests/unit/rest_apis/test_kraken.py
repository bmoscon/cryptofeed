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
        data = kraken.recent_spread_data({"pair": "adacad"})
        assert len(data['result']['ADACAD']) > 0


if __name__ == '__main__':
    unittest.main()

kraken = Rest('config.yaml').kraken
kraken._post_public("/public/Assets")

import requests
resp = requests.post(
"{}{}".format(kraken.api, "/public/Spread"),
data = {"pair": "adacad"}
)
resp.json()
