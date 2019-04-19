from time import time, sleep
import hashlib
import hmac
import requests
import json
import base64
import logging
from decimal import Decimal

from sortedcontainers.sorteddict import SortedDict as sd
import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import GEMINI, BID, ASK, UNSUPPORTED
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std, feed_to_exchange


LOG = logging.getLogger('rest')


# https://docs.gemini.com/rest-api/#introduction
# For public API entry points, we limit requests to 120 requests per minute, and recommend that you do not exceed 1 request per second.
# For private API entry points, we limit requests to 600 requests per minute, and recommend that you not exceed 5 requests per second.
class Gemini(API):
    ID = GEMINI

    api = "https://api.gemini.com"
    sandbox_api = "https://api.sandbox.gemini.com"

    def _get(self, command: str, retry, retry_wait, params=None):
        api = self.api if not self.sandbox else self.sandbox_api

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            resp = requests.get(f"{api}{command}", params=params)
            self._handle_error(resp, LOG)
            return resp.json()
        return helper()

    def _post(self, command: str, payload=None):
        if not payload:
            payload = {}
        payload['request'] = command
        payload['nonce'] = int(time() * 1000)

        api = self.api if not self.sandbox else self.sandbox_api
        api = f"{api}{command}"

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
        self._handle_error(resp, LOG)

        return resp.json()

    # Public Routes
    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get(f"/v1/pubticker/{sym}", retry, retry_wait)
        return {'pair': symbol,
                'feed': self.ID,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
               }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get(f"/v1/book/{sym}", retry, retry_wait)
        return {
            BID: sd({
                Decimal(u['price']): Decimal(u['amount'])
                for u in data['bids']
            }),
            ASK: sd({
                Decimal(u['price']): Decimal(u['amount'])
                for u in data['asks']
            })
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        sym = pair_std_to_exchange(symbol, self.ID)
        params = {'limit_trades': 500}
        if start:
            params['since'] = int(pd.Timestamp(start).timestamp() * 1000)
        if end:
            end_ts = int(pd.Timestamp(end).timestamp() * 1000)

        def _trade_normalize(trade):
            return {
                'feed': self.ID,
                'order_id': trade['tid'],
                'pair': sym,
                'side': trade['type'],
                'amount': Decimal(trade['amount']),
                'price': Decimal(trade['price']),
                'timestamp': trade['timestampms'] / 1000.0
            }

        while True:
            data = reversed(self._get(f"/v1/trades/{sym}?", retry, retry_wait, params=params))
            if end:
                data = [_trade_normalize(d) for d in data if d['timestampms'] <= end_ts]
            else:
                data = [_trade_normalize(d) for d in data]
            yield data

            if start:
                try:
                    params['since'] = int(data[-1]['timestamp'] * 1000) + 1
                except:
                    print(data)
            if len(data) < 500:
                break
            if not start and not end:
                break
            # GEMINI rate limits to 120 requests a minute
            sleep(0.5)

    # Order Placement API

    def place_order(self, pair: str, side: str, order_type: str, amount: Decimal, price: Decimal, client_order_id=None, options=None):
        ot = feed_to_exchange(self.ID, order_type)
        sym = pair_std_to_exchange(self.ID, pair)

        parameters = {
            'type': ot,
            'symbol': sym,
            'side': side,
            'amount': str(amount),
            'price': str(price)
        }

        if client_order_id:
            parameters['client_order_id'] = client_order_id

        return self._post("/v1/order/new", parameters)

    def cancel_order(self, order_id):
        return self._post("/v1/order/cancel", {'order_id': order_id})

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
            timestamp	  timestamp	Optional. Only return trades on or after this timestamp. See Data Types: Timestamps for more information.
                                    If not present, will show the most recent orders.
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

    def transfers(self, parameters=None):
        """
        Parameters:
            timestamp	timestamp	Optional. Only return transfers on or after this timestamp. See Data Types: Timestamps for more
                                    information. If not present, will show the most recent transfers.
            limit_transfers	integer	Optional. The maximum number of transfers to return. The default is 10 and the maximum is 50.
        """
        return self._post("/v1/transfers", parameters)

    def new_deposit_address(self, currency: str, parameters=None):
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
