'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from time import time
import hashlib
import hmac
import requests
import urllib
from decimal import Decimal
import calendar
import logging

import pandas as pd
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import POLONIEX, BUY, SELL, BID, ASK
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std


LOG = logging.getLogger('rest')


# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class Poloniex(API):
    ID = POLONIEX

    # for public_api add "public" to the url, for trading add "tradingApi" (example: https://poloniex.com/public)
    rest_api = "https://poloniex.com/"


    def _get(self, command: str, options=None, retry=None, retry_wait=0):
        base_url = f"{self.rest_api}public?command={command}"

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            resp = requests.get(base_url, params=options)
            self._handle_error(resp, LOG)
            return resp.json()
        return helper()

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
        resp = requests.post(f"{self.rest_api}tradingApi?command={command}", headers=headers, data=paybytes)
        self._handle_error(resp, LOG)

        return resp.json()

    # Public API Routes
    def ticker(self, symbol: str, retry=None, retry_wait=10):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get("returnTicker", retry=retry, retry_wait=retry_wait)
        return {'pair': symbol,
                'feed': self.ID,
                'bid': Decimal(data[sym]['lowestAsk']),
                'ask': Decimal(data[sym]['highestBid'])
            }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get("returnOrderBook", {'currencyPair': sym}, retry=retry, retry_wait=retry_wait)
        return {
                BID: sd({
                    Decimal(u[0]): Decimal(u[1])
                    for u in data['bids']
                }),
                ASK: sd({
                    Decimal(u[0]): Decimal(u[1])
                    for u in data['asks']
                })
            }

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

        if not start:
            yield map(lambda x: self._trade_normalize(x, symbol), helper())

        else:
            if not end:
                end = pd.Timestamp.utcnow()
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

    def place_order(self, pair: str, side: str, type: str, amount: str, price: str, fill_or_kill: str, immediate_or_cancel: str, post_only: str):
        parameters = {
            'currencyPair': pair,
            'amount': amount,
            'rate': price
        }

        if fill_or_kill is not None:
            parameters['fillOrKill'] = fill_or_kill

        if immediate_or_cancel is not None:
            parameters['immediateOrCancel'] = immediate_or_cancel

        if post_only is not None:
            parameters['postOnly'] = post_only

        return self._post(side, parameters)

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
