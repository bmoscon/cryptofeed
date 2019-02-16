from time import time
import hashlib
import hmac
import requests
import urllib
from decimal import Decimal
import calendar
import logging

import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import POLONIEX, BUY, SELL
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std


LOG = logging.getLogger('rest')


# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class Poloniex(API):
    ID = POLONIEX

    # for public_api add "public" to the url, for trading add "tradingApi" (example: https://poloniex.com/public)
    rest_api = "https://poloniex.com/"

    def _get(self, command: str, options=None):
        base_url = "{}public?command={}".format(self.rest_api, command)

        resp = requests.get(base_url, params=options)
        self.handle_error(resp, LOG)

        return resp.json()

    def _post(self, command: str, payload=None):
        if not payload:
            payload = {}
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
        self.handle_error(resp, LOG)

        return resp.json()

    # Public API Routes

    def tickers(self):
        return self._get("returnTicker")

    def past_day_volume(self):
        return self._get("return24hVolume")

    def order_books(self, options=None):
        """
        options: currencyPair=BTC_NXT depth=10
        """
        return self._get("returnOrderBook", options)

    def _trade_normalize(self, trade, symbol):
        return {
            'timestamp': trade['date'],
            'pair': pair_exchange_to_std(symbol),
            'id': trade['tradeID'],
            'feed': self.ID,
            'side': BUY if trade['type'] == 'buy' else SELL,
            'amount': Decimal(trade['amount']),
            'price': Decimal(trade['rate'])
        }

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        symbol = pair_std_to_exchange(symbol, self.ID)

        @request_retry(self.ID, retry, retry_wait)
        def helper(s=None, e=None):
            data = self._get("returnTradeHistory", {'currencyPair': symbol, 'start': s, 'end': e})
            data.reverse()
            return data

        if not start or not end:
            yield map(lambda x: self._trade_normalize(x, symbol), helper())

        else:
            start = pd.Timestamp(start)
            end = pd.Timestamp(end) - pd.Timedelta(nanoseconds=1)

            start = int(calendar.timegm(start.utctimetuple()))
            end = int(calendar.timegm(end.utctimetuple()))

            s = start
            e = start + 21600
            while True:
                if e > end:
                    e = end

                yield map(lambda x: self._trade_normalize(x, symbol), helper(s=s, e=e))

                s = e
                e += 21600
                if s >= end:
                    break

    def chart_data(self, options=None):
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

    def complete_balances(self, payload=None):
        """
        set {"account": "all"} to return margin and lending accounts
        """
        return self._post("returnCompleteBalances", payload)

    def deposit_addresses(self):
        return self._post("returnDepositAddresses")

    def generate_new_address(self, payload=None):
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

    def open_orders(self, payload=None):
        """
        Data FORMAT
        {"currencyPair": <pair>} ("all" will return open orders for all markets)
        """
        if not payload:
            payload = {"currencyPair": "all"}
        return self._post("returnOpenOrders", payload)

    def trade_history(self, payload=None):
        """
        Data FORMAT
        {
        "currencyPair": <pair>,
        "start": <UNIX Timestamp> (optional),
        "end": <UNIX Timestamp> (optional)
        "limit": int (optional, up to 10,000. only 500 if not specified)
        } ("all" will return open orders for all markets)
        """
        if not payload:
            payload = {"currencyPair": "all"}
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

    def cancel_order(self, order_id):
        return self._post("cancelOrder", {"orderNumber": order_id})

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

    def available_account_balances(self, payload=None):
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
