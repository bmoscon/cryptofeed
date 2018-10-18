from time import time
import hashlib, hmac, requests, urllib, json, base64

from cryptofeed.rest.api import API
from cryptofeed.feeds import KRAKEN
from cryptofeed.log import get_logger

LOG = get_logger('rest', 'rest.log')

class Kraken(API):
    ID = KRAKEN

    api = "https://api.kraken.com/0"

    def _post_public(self, command: str):
        url = "{}{}".format(self.api, command)

        resp = requests.get(url)

        if resp.status_code != 200:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        return resp.json()

    def _post_private(self, payload = {}):
        # API-Key = API key
        # API-Sign = Message signature using HMAC-SHA512 of (URI path + SHA256(nonce + POST data)) and base64 decoded secret API key
        payload['nonce'] = int(time() * 1000)


    # public API
    def get_server_time(self):
        return self._post_public("/public/Time")

    def get_asset_info(self, payload = {}):
        """
        Parameters (optional):
            asset: comma delimited list of asset types (currencies)
            aclass: asset class
        """
        return self._post_public("/public/Assets", payload)

    def get_tradeable_pairs(self, payload = {}):
        """
        Parameters:
            info: info = all info (default), leverage = leverage info, fees = fees schedule, margin = margin info
            pair: comma delimited list of asset pairs
        """
        return self._post_public("/public/AssetPairs", payload)

    def get_ticker_info(self, payload: dict):
        """
        Parameters:
            pair: comma delimited list of asset pairs (required)
        """
        return self._post_public("/public/Ticker", payload)

    def get_ohlc_data(self, payload = {}):
        """
        Parameters:
            pair = asset pair to get OHLC data for (required)
            interval = time frame interval in minutes (optional):
            	1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
            since = return committed OHLC data since given id (optional.  exclusive)
        """
        return self._post_public("/public/OHLC", payload)


    def get_order_book(self, payload = {}):
        """
        Parameters:
            pair = asset pair to get market depth for
            count = maximum number of asks/bids (optional)
        """
        return self._post_public("/public/Depth", payload)


    def get_recent_trades(self, payload = {}):
        """
        Parameters:
            pair = asset pair to get trade data for
            since = return trade data since given id (optional.  exclusive)
        """
        return self._post_public("/public/Trades", payload)

    def get_recent_spread_data(self, payload = {}):
        """
        Parameters:
            pair = asset pair to get spread data for
            since = return spread data since given id (optional.  inclusive)
        """
        return self._post_public("/public/Spread", payload)
