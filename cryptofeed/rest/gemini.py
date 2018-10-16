from time import time
import hashlib, hmac, requests, urllib, json, base64

from cryptofeed.rest.api import API
from cryptofeed.feeds import GEMINI
from cryptofeed.log import get_logger

LOG = get_logger('rest', 'rest.log')

# https://docs.gemini.com/rest-api/#introduction
# For public API entry points, we limit requests to 120 requests per minute, and recommend that you do not exceed 1 request per second.
# For private API entry points, we limit requests to 600 requests per minute, and recommend that you not exceed 5 requests per second.
class Gemini(API):
    ID = GEMINI

    api = "https://api.gemini.com"
    sandbox_api = "https://api.sandbox.gemini.com"

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
        payload['request'] = command
        payload['nonce'] = int(time() * 1000)

        api = self.api
        if self.sandbox:
            api = self.sandbox_api

        api = "{}{}".format(api, command)

        b64_payload = base64.b64encode(json.dumps(payload).encode('utf-8'))
        signature = hmac.new(self.key_secret.encode('utf-8'), b64_payload, hashlib.sha384).hexdigest()

        headers = {
            'Content-Type': "text/plain",
            'Content-Length': "0",
            'X-GEMINI-APIKEY': self.key_id,
            'X-GEMINI-PAYLOAD': b64_payload,
            'X-GEMINI-SIGNATURE': signature,
            'Cache-Control': "no-cache"
        }

        resp = requests.post(api, headers=headers)
        if resp.status_code >= 300:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        # return response.content
        return resp.json()


    # Public Routes

    def symbols(self):
        return self._get("/v1/symbols")

    def ticker(self, symbol: str):
        return self._get("/v1/pubticker/{}".format(symbol))

    def current_order_book(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            limit_bids	integer	Optional. Limit the number of bids (offers to buy) returned. Default is 50. May be 0 to return the full order book on this side.
            limit_asks	integer	Optional. Limit the number of asks (offers to sell) returned. Default is 50. May be 0 to return the full order book on this side.
        """
        return self._get("/v1/book/{}".format(symbol), parameters)

    def trade_history(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            since	        timestamp	Optional. Only return trades after this timestamp. See Data Types: Timestamps for more information. If not present, will show the most recent trades. For backwards compatibility, you may also use the alias 'since'.
            limit_trades	integer	    Optional. The maximum number of trades to return. The default is 50.
            include_breaks	boolean	    Optional. Whether to display broken trades. False by default. Can be '1' or 'true' to activate
        """
        return self._get("/v1/trades/{}".format(symbol), parameters)

    def current_auction(self, symbol: str):
        return self._get("/v1/auction/{}".format(symbol))

    def auction_history(self, symbol: str, parameters = {}):
        """
        Signature:
            symbol: str, parameters: dict of params for get query
        Parameters:
            since	                timestamp	Optional. Only returns auction events after the specified timestamp. If not present or empty, will show the most recent auction events. You can also use the alias 'timestamp'.
            limit_auction_results	integer	    Optional. The maximum number of auction events to return. The default is 50.
            include_indicative	    boolean	    Optional. Whether to include publication of indicative prices and quantities. True by default, true to explicitly enable, and false to disable
        """
        return self._get("/v1/auction/{}/history".format(symbol), parameters)


    # Order Placement API

    def new_order(self, parameters):
        """
        Parameters:
            client_order_id	string	Recommended. A client-specified order id
            symbol	string	The symbol for the new order
            amount	string	Quoted decimal amount to purchase
            min_amount	string	Optional. Minimum decimal amount to purchase, for block trades only
            price	string	Quoted decimal amount to spend per unit
            side	string	"buy" or "sell"
            type	string	The order type. Only "exchange limit" supported through this API
            options	array	Optional. An optional array containing at most one supported order execution option. See Order execution options for details
        """
        return self._post("/v1/order/new", parameters)


    def cancel_order(self, parameters):
        """
        Parameters:
            order_id	integer	The order ID given by /order/new
        """
        return self._post("/v1/order/cancel", parameters)


    def cancel_all_session_orders(self):
        return self._post("/v1/order/cancel/session")


    def cancel_all_active_orders(self):
        return self._post("/v1/order/cancel/all")


    # Order Status API

    def order_status(self, parameters):
        """
        Parameters:
            order_id	integer	the order ID to be queried
        """
        return self._post("/v1/order/status", parameters)

    def get_active_orders(self):
        return self._post("/v1/orders")


    def get_past_trades(self, parameters):
        """
        Parameters:
            symbol	string	The symbol to retrieve trades for
            limit_trades	integer	Optional. The maximum number of trades to return. Default is 50, max is 500.
            timestamp	timestamp	Optional. Only return trades on or after this timestamp. See Data Types: Timestamps for more information. If not present, will show the most recent orders.
        """
        return self._post("/v1/mytrades", parameters)


    # Fee and Volume Volume API
    def get_notional_volume(self):
        return self._post("/v1/notionalvolume")

    def get_trade_volume(self):
        return self._post("/v1/tradevolume")


    # Fund Managment API
    def get_available_balances(self):
        return self._post("/v1/balances")

    def transfers(self, parameters={}):
        """
        Parameters:
            timestamp	timestamp	Optional. Only return transfers on or after this timestamp. See Data Types: Timestamps for more information. If not present, will show the most recent transfers.
            limit_transfers	integer	Optional. The maximum number of transfers to return. The default is 10 and the maximum is 50.
        """
        return self._post("/v1/transfers", parameters)

    def new_deposit_address(self, currency: str, parameters={}):
        """
        Parameters:
            label	string	Optional. label for the deposit address
        """
        uri = "/v1/deposit/{}/newAddress".format(currency)
        return self._post(uri, parameters)

    def withdraw_crypto_to_address(self, currency: str, parameters):
        """
        Parameters:
            address	string	Standard string format of a whitelisted cryptocurrency address.
            amount	string	Quoted decimal amount to withdraw
        """
        uri = "/v1/withdraw/{}".format(currency)
        parameters["request"] = uri
        return self._post(uri, parameters)

    def heartbeat(self):
        return self._post("/v1/heartbeat")
