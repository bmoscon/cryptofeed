from time import time
import hashlib, hmac, requests, urllib

from cryptofeed.rest.api import API
from cryptofeed.feeds import POLONIEX
from cryptofeed.log import get_logger

LOG = get_logger('rest', 'rest.log')

# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class Poloniex(API):
    ID = POLONIEX

    # for public_api add "public" to the url, for trading add "tradingApi" (example: https://poloniex.com/public)
    rest_api = "https://poloniex.com/"

    def _get(self, command: str, options = {}):
        base_url = "{}public?command={}".format(self.rest_api, command)

        # loop over dictionary of options and add them as query parameters to the url
        # example: currencyPair=BTC_NXT&depth=10
        for key, val in options.items():
            base_url = "{}&{}={}".format(base_url, key, val)

        resp = requests.get(base_url)

        if resp.status_code != 200:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        return resp.json()


    def _post(self, command: str, payload = {}):
        # need to sign the payload, referenced https://stackoverflow.com/questions/43559332/python-3-hash-hmac-sha512
        payload['command'] = command
        payload['nonce'] = int(time() * 1000)

        paybytes = urllib.parse.urlencode(payload).encode('utf8')
        sign = hmac.new(bytes(self.key_secret, 'utf8'), paybytes, hashlib.sha512).hexdigest()

        headers = {
            "Key": self.key_id,
            "Sign": sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        resp = requests.post("{}tradingApi?command={}".format(self.rest_api, command), headers=headers, data=paybytes)
        if resp.status_code >= 300:
            LOG.error("%s: Status code %d", self.ID, resp.status_code)
            LOG.error("%s: Headers: %s", self.ID, resp.headers)
            LOG.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

        return resp.json()

    # Public API Routes

    def tickers(self):
        return self._get("returnTicker")

    def past_day_volume(self):
        return self._get("return24hVolume")

    def order_books(self, options = {}):
        """
        options: currencyPair=BTC_NXT depth=10
        """
        return self._get("returnOrderBook", options)

    def all_trade_history(self, options = {}):
        """
        options: currencyPair=BTC_NXT start=1410158341 end=1410499372
        """
        return self._get("returnTradeHistory", options)

    def chart_data(self, options = {}):
        """
        options: currencyPair=BTC_XMR start=1405699200 end=9999999999 period=14400
        """
        return self._get("returnChartData", options)

    def currencies(self):
        return self._get("returnCurrencies")

    # Trading API Routes
    # Private endpoints require a nonce, which must be an integer greater than the previous nonce used
    def balances(self):
        return self._post("returnBalances")

    def complete_balances(self, payload={}):
        """
        set {"account": "all"} to return margin and lending accounts
        """
        return self._post("returnCompleteBalances", payload)

    def deposit_addresses(self):
        return self._post("returnDepositAddresses")

    def generate_new_address(self, payload={}):
        """
        Generates a new deposit address for the currency specified by the "currency"
        """
        return self._post("generateNewAddress", payload)

    def deposit_withdrawals(self, payload):
        """
        Data FORMAT
        {"start": <UNIX Timestamp>,"end": <UNIX Timestamp>}
        """
        return self._post("returnDepositsWithdrawals", payload)

    def open_orders(self, payload={"currencyPair": "all"}):
        """
        Data FORMAT
        {"currencyPair": <pair>} ("all" will return open orders for all markets)
        """
        return self._post("returnOpenOrders", payload)

    def trade_history(self, payload={"currencyPair": "all"}):
        """
        Data FORMAT
        {
        "currencyPair": <pair>,
        "start": <UNIX Timestamp> (optional),
        "end": <UNIX Timestamp> (optional)
        "limit": int (optional, up to 10,000. only 500 if not specified)
        } ("all" will return open orders for all markets)
        """
        return self._post("returnTradeHistory", payload)

    def order_trades(self, payload):
        """
        Data FORMAT
        {"orderNumber": int} (if order number doesn't exist you'll get an error)
        """
        return self._post("returnOrderTrades", payload)

    def order_status(self, payload):
        """
        Data FORMAT
        {"orderNumber": int} (if order number is not open or not yours you'll get an error)
        """
        return self._post("returnOrderStatus", payload)

    def buy(self, payload):
        """
        Data FORMAT
        {
        "currencyPair": <pair>,
        "rate": <rate>,
        "amount": <amount>,
        "fillOrKill" (optional)
        "immediateOrCancel" (optional)
        "postOnly" (optional)
        }
        "fillOrKill", "immediateOrCancel", "postOnly" to 1
        """
        return self._post("buy", payload)

    def sell(self, payload):
        """
        Data FORMAT
        {
        "currencyPair": <pair>,
        "rate": <rate>,
        "amount": <amount>,
        "fillOrKill" (optional)
        "immediateOrCancel" (optional)
        "postOnly" (optional)
        }
        "fillOrKill", "immediateOrCancel", "postOnly" to 1
        """
        return self._post("sell", payload)

    def cancel_order(self, payload):
        """
        Data FORMAT
        {"orderNumber": int}
        """
        return self._post("cancelOrder", payload)

    def move_order(self, payload):
        """
        Data FORMAT
        {"orderNumber": <order>, "rate": <rate>, "amount": <amount>(optional)}
        """
        return self._post("moveOrder", payload)

    def withdraw(self, payload):
        """
        Data FORMAT
        "currency", "amount", and "address".
        """
        return self._post("withdraw", payload)

    def available_account_balances(self, payload={}):
        """
        "account" (optional)
        """
        return self._post("returnAvailableAccountBalances", payload)

    def tradable_balances(self):
        return self._post("returnTradableBalances")

    def transfer_balance(self, payload):
        """
        Data FORMAT
        "currency", "amount", "fromAccount", and "toAccount"
        """
        return self._post("transferBalance", payload)
