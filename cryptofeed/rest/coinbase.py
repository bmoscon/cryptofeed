import time, json, hashlib, hmac, requests, base64
from time import sleep
from datetime import datetime as dt

import pandas as pd

from cryptofeed.rest.api import API
from cryptofeed.feeds import COINBASE
from cryptofeed.log import get_logger
from cryptofeed.standards import pair_std_to_exchange

REQUEST_LIMIT = 10
LOG = get_logger('rest', 'rest.log')

# API Docs https://docs.gdax.com/
class Coinbase(API):
    ID = COINBASE

    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"


    def _generate_signature(self, endpoint: str, method: str, body = ''):
        timestamp = str(time.time())
        message = ''.join([timestamp, method, endpoint, body])
        hmac_key = base64.b64decode(self.key_secret)
        signature = hmac.new(hmac_key, message.encode('ascii'), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'CB-ACCESS-KEY': self.key_id, # The api key as a string.
            'CB-ACCESS-SIGN': signature_b64, # The base64-encoded signature (see Signing a Message).
            'CB-ACCESS-TIMESTAMP': timestamp, # A timestamp for your request.
            'CB-ACCESS-PASSPHRASE': self.key_passphrase, # The passphrase you specified when creating the API key
            'Content-Type': 'Application/JSON',
        }

    def _pagination(self, endpoint: str, body=None):
        if body is None:
            return endpoint

        if 'before' in body:
            if '?' in endpoint:
                endpoint = '{}&before={}'.format(endpoint, 'before')
            else:
                endpoint = '{}?before={}'.format(endpoint, 'before')
        if 'after' in body:
            if '?' in endpoint:
                endpoint = '{}&after={}'.format(endpoint, 'after')
            else:
                endpoint = '{}?after={}'.format(endpoint, 'after')
        if 'limit' in body:
            endpoint = '{}?limit={}'.format(endpoint, 'limit')

        return endpoint

    def _make_request(self, method: str, endpoint: str, header: dict, body=None, retry=None, retry_wait=0):
        api = self.api
        if self.sandbox:
            api = self.sandbox_api

        while True:
            try:
                if method == "GET":
                    resp = requests.get('{}{}'.format(api, endpoint), headers=header)
                elif method == "POST":
                    resp = requests.post('{}{}'.format(api, endpoint), json=body, headers=header)
                elif method == "DELETE":
                    resp = requests.delete('{}{}'.format(api, endpoint), headers=header)
            except TimeoutError as e:
                LOG.warning("%s: Timeout - %s", self.ID, e)
                if retry is not None:
                    if retry == 0:
                        raise
                    else:
                        retry -= 1
                sleep(retry_wait)
                continue
            except requests.exceptions.ConnectionError as e:
                LOG.warning("%s: Connection error - %s", self.ID, e)
                if retry is not None:
                    if retry == 0:
                        raise
                    else:
                        retry -= 1
                sleep(retry_wait)
                continue

            # 400 Bad Request – Invalid request format
            # 401 Unauthorized – Invalid API Key
            # 403 Forbidden – You do not have access to the requested resource
            # 404 Not Found
            # 500 Internal Server Error – We had a problem with our server
            if resp.status_code != 200:
                LOG.error("%s: Status code %d", self.ID, resp.status_code)
                LOG.error("%s: Headers: %s", self.ID, resp.headers)
                LOG.error("%s: Resp: %s", self.ID, resp.text)
                resp.raise_for_status()

            return resp.json()


    def _get_fills(self, symbol=None, retry=None, retry_wait=0, start_date=None, end_date=None):
        endpoint = '/fills'
        if symbol is not None:
            symbol = pair_std_to_exchange(symbol, self.ID)
            endpoint = '{}?product_id={}'.format(endpoint, symbol)

        header = self._generate_signature(endpoint, "GET")
        data = self._make_request("GET", endpoint, header, retry=retry)

        if data == []:
            LOG.warning("%s: No data", self.ID)
        elif start_date is not None and end_date is not None:
            # filter out data not in specified range
            data_in_range = []
            start_time = pd.Timestamp(start_date).to_pydatetime()
            end_time = pd.Timestamp(end_date).to_pydatetime()
            for entry in data:
                entry_time = dt.strptime(entry['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ")

                if entry_time >= start_time and entry_time <= end_time:
                    data_in_range.append(entry)
            data = data_in_range

        data = list(map(self._trade_normalization, data))
        return data


    def _get_orders(self, body):
        """
        https://docs.gdax.com/?python#list-orders
        """
        endpoint = "/orders"
        if 'status' in body:
            for status in body['status']:
                if 'status' not in endpoint:
                    endpoint = '{}?status={}'.format(endpoint, status)
                else:
                    endpoint = '{}&status{}'.format(endpoint, status)

        if 'product_id' in body:
            product_id = pair_std_to_exchange(body['product_id'], self.ID)
            if 'status' in endpoint:
                endpoint = '{}&product_id={}'.format(endpoint, product_id)
            else:
                endpoint = '{}?product_id={}'.format(endpoint, product_id)

        endpoint = self._pagination(endpoint, body)

        header = self._generate_signature(endpoint, "GET")
        data = self._make_request("GET", endpoint, header)
        data = list(map(self._trade_normalization, data))

        return data


    def _get_order(self, order_id):
        """
        https://docs.gdax.com/?python#get-an-order
        """
        endpoint = "/orders/{}".format(order_id)
        header = self._generate_signature(endpoint, "GET")
        data = self._make_request("GET", endpoint, header)

        return data


    def _post_order(self, body, retry=None, retry_wait=0):
        """
        https://docs.gdax.com/?python#place-a-new-order
        """
        endpoint = "/orders"
        header = self._generate_signature(endpoint, "POST", body=json.dumps(body))
        data = self._make_request("POST", endpoint, header, body, retry=retry, retry_wait=retry_wait)

        return data


    def _delete_order(self, order_id=None):
        endpoint = "/orders"
        if order_id is not None:
            endpoint = '{}/{}'.format(endpoint, order_id)

        header = self._generate_signature(endpoint, "DELETE")
        self._make_request("DELETE", endpoint, header)

    def _get(self, endpoint):
        header = self._generate_signature(endpoint, "GET")
        return self._make_request("GET", endpoint, header)

    def _post(self, endpoint, body):
        header = self._generate_signature(endpoint, "POST", body=json.dumps(body))
        return self._make_request("POST", endpoint, header, body)


    def fills(self, symbol=None, start=None, end=None, retry=None, retry_wait=10):
        """
        data format

        {
            "trade_id": 74,
            "product_id": "BTC-USD",
            "price": "10.00",
            "size": "0.01",
            "order_id": "d50ec984-77a8-460a-b958-66f114b0de9b",
            "created_at": "2014-11-07T22:19:28.578544Z",
            "liquidity": "T",
            "fee": "0.00025",
            "settled": true,
            "side": "buy"
        }
        """
        return self._get_fills(symbol=symbol, retry=retry, retry_wait=retry_wait, start_date=start, end_date=end)


    def execute_trades(self, trades_to_make: list):
        """
        https://docs.gdax.com/?python#place-a-new-order
        data format
        {
            "size": "0.01",
            "price": "0.100",
            "side": "buy",
            "product_id": "BTC-USD"
        }

        Param descriptions
        client_oid	[optional] Order ID selected by you to identify your order
        type	[optional] limit or market (default is limit)
        side	buy or sell
        product_id	A valid product id
        stp	[optional] Self-trade prevention flag
        stop	[optional] Either loss or entry. Requires stop_price to be defined.
        stop_price	[optional] Only if stop is defined. Sets trigger price for stop order.

        LIMIT ORDER PARAMETERS
        Param	Description
        price	Price per bitcoin
        size	Amount of BTC to buy or sell
        time_in_force	[optional] GTC, GTT, IOC, or FOK (default is GTC)
        cancel_after	[optional]* min, hour, day
        post_only	[optional]** Post only flag
        * Requires time_in_force to be GTT

        ** Invalid when time_in_force is IOC or FOK

        MARKET ORDER PARAMETERS
        Param	Description
        size	[optional]* Desired amount in BTC
        funds	[optional]* Desired amount of quote currency to use
        * One of size or funds is required.
        """

        responses = []
        for trade in trades_to_make:
            responses.append(self._trade_normalization(
                self._post_order(trade, retry=None, retry_wait=0)
            ))

        return responses


    def cancel_orders(self, order_id=None):
        self._delete_order(order_id)


    def get_orders(self, body):
        """
        body should be
        {
            'status':['open', 'pending', 'active'],
            'product_id': 'BTC-USD' (optional)
        }
        """
        return self._get_orders(body)


    def get_order(self, order_id: str):
        return self._trade_normalization(self._get_order(order_id))

    def get_accounts(self):
        return self._get("/accounts")

    def get_account(self, account_id: str):
        endpoint = "/accounts/{}".format(account_id)
        return self._get(endpoint)

    def get_account_history(self, account_id: str, pagination=None):
        endpoint = "/accounts/{}/ledger".format(account_id)
        endpoint = self._pagination(endpoint, pagination)

        return self._get(endpoint)

    def get_holds(self, account_id: str, pagination=None):
        endpoint = "/accounts/{}/holds".format(account_id)
        endpoint = self._pagination(endpoint, pagination)

        return self._get(endpoint)


    def deposit_funds(self, body):
        """
        Deposit funds from a payment method to the account the api key is associated with.

        data format
        {
            "amount": 10.00,
            "currency": "USD",
            "payment_method_id": "bc677162-d934-5f1a-968c-a496b1c1270b"
        }
        """
        return self._post("/deposits/payment-method", body)


    def deposit_coinbase(self, body):
        """
        Deposit funds from a different coinbase account into the account the api key is associated with.

        data format
        {
            "amount": 10.00,
            "currency": "BTC",
            "coinbase_account_id": "c13cd0fc-72ca-55e9-843b-b84ef628c198",
        }
        """
        return self._post("/deposits/coinbase-account", body)


    def withdrawal_funds(self, body):
        """
        Withdrawal funds from the account the api key is associated with to the specified account
        data format
        {
            "amount": 10.00,
            "currency": "USD",
            "payment_method_id": "bc677162-d934-5f1a-968c-a496b1c1270b"
        }
        """
        return self._post("/withdrawals/payment-method", body)


    def withdrawal_coinbase(self, body):
        """
        Withdrawal funds from the account the api key is associated with to the specified coinbase account
        data format
        {
            "amount": 10.00,
            "currency": "BTC",
            "coinbase_account_id": "c13cd0fc-72ca-55e9-843b-b84ef628c198",
        }
        """
        return self._post("/withdrawals/coinbase-account", body)


    def withdrawal_crypto(self, body):
        """
        Withdrawal funds from the account the api key is associated with to the specified crypto address
        data format
        {
            "amount": 10.00,
            "currency": "BTC",
            "crypto_address": "0x5ad5769cd04681FeD900BCE3DDc877B50E83d469"
        }
        """
        return self._post("/withdrawals/crypto", body)

    def list_payment_methods(self):
        return self._get("/payment-methods")

    def list_coinbase_accounts(self):
        return self._get("/coinbase-accounts")


    def _trade_normalization(self, trade: dict) -> dict:
        trade_data = {
            'timestamp': trade['created_at'],
            'pair': trade['product_id'],
            'feed': self.ID,
            'side': trade['side'],
            'amount': trade['size'],
            "settled": trade["settled"]
        }
        if 'order_id' in trade:
            trade_data['id'] = trade['order_id']
            trade_data['price'] = trade['price']
            trade_data['fee'] = trade['fee']
        else:
            trade_data['type'] = trade['type']
            trade_data['id'] = trade['id']
            trade_data['type'] = trade['type']
            trade_data["fill_fees"] = trade["fill_fees"]
            trade_data["filled_size"] = trade["filled_size"]
            trade_data["executed_value"] = trade["executed_value"]
            trade_data["status"] = trade["status"]

        return trade_data
