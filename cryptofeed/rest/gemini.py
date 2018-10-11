from time import time
import hashlib, hmac, requests, urllib

from cryptofeed.rest.api import API
from cryptofeed.feeds import GEMINI
from cryptofeed.log import get_logger

LOG = get_logger('rest', 'rest.log')

# https://docs.gemini.com/rest-api/#introduction
# For public API entry points, we limit requests to 120 requests per minute, and recommend that you do not exceed 1 request per second.
# For private API entry points, we limit requests to 600 requests per minute, and recommend that you not exceed 5 requests per second.
class Gemini(API):
    ID = GEMINI

    api = "https://api.gemini.com/v1/"
    sandbox_api = "https://api.sandbox.gemini.com/v1/"

    def _get(self, command: str, options = {}):
        api = self.api
        if self.sandbox:
            api = self.sandbox_api

        base_url = "{}{}".format(api, command)

        # loop over dictionary of options and add them as query parameters to the url
        # example: currencyPair=BTC_NXT&depth=10
        for key, val in options.items():
            if "?" not in base_url:
                base_url = "{}?{}={}".format(base_url, key, val)
                continue

            base_url = "{}&{}={}".format(base_url, key, val)

        resp = requests.get(base_url)

        if resp.status_code != 200:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        return resp.json()


    def _post(self, command: str, payload = {}):
        api = self.api
        if self.sandbox:
            api = self.sandbox_api

        payload['command'] = command
        payload['nonce'] = int(time() * 1000)

        encoded_payload = json.dumps(payload)
        b64 = base64.b64encode(encoded_payload)
        signature = hmac.new(bytes(self.key_secret, 'utf8'), b64, hashlib.sha384).hexdigest()

        headers = {
            'Content-Type': "text/plain",
            'Content-Length': "0",
            'X-GEMINI-APIKEY': self.key_id,
            'X-GEMINI-PAYLOAD': b64,
            'X-GEMINI-SIGNATURE': signature,
            'Cache-Control': "no-cache"
        }

        resp = requests.post(api, data=None, headers=headers, timeout=timeout, verify=False)
        if resp.status_code >= 300:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        # return response.content
        return resp.json()


    # Public Routes

    def symbols(self):
        return self._get("symbols")

    def ticker(self, symbol: str):
        return self._get("pubticker/{}".format(symbol))

    def current_order_book(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            limit_bids	integer	Optional. Limit the number of bids (offers to buy) returned. Default is 50. May be 0 to return the full order book on this side.
            limit_asks	integer	Optional. Limit the number of asks (offers to sell) returned. Default is 50. May be 0 to return the full order book on this side.
        """
        return self._get("book/{}".format(symbol), parameters)

    def trade_history(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            since	        timestamp	Optional. Only return trades after this timestamp. See Data Types: Timestamps for more information. If not present, will show the most recent trades. For backwards compatibility, you may also use the alias 'since'.
            limit_trades	integer	    Optional. The maximum number of trades to return. The default is 50.
            include_breaks	boolean	    Optional. Whether to display broken trades. False by default. Can be '1' or 'true' to activate
        """
        return self._get("trades/{}".format(symbol), parameters)

    def current_auction(self, symbol: str):
        return self._get("auction/{}".format(symbol))

    def auction_history(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            since	                timestamp	Optional. Only returns auction events after the specified timestamp. If not present or empty, will show the most recent auction events. You can also use the alias 'timestamp'.
            limit_auction_results	integer	    Optional. The maximum number of auction events to return. The default is 50.
            include_indicative	    boolean	    Optional. Whether to include publication of indicative prices and quantities. True by default, true to explicitly enable, and false to disable
        """
        return self._get("auction/{}/history".format(symbol), parameters)
