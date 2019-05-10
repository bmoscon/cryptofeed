'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
import json
import hashlib
import hmac
import requests
import base64
from time import sleep
import logging
from decimal import Decimal

import pandas as pd
from sortedcontainers.sorteddict import SortedDict as sd
from pytz import UTC

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import COINBASE, BUY, SELL, MARKET, LIMIT, FILLED, OPEN, PARTIAL, PENDING, CANCELLED, BID, ASK
from cryptofeed.standards import normalize_trading_options, timestamp_normalize


REQUEST_LIMIT = 10
LOG = logging.getLogger('rest')


# API Docs https://docs.gdax.com/
class Coinbase(API):
    ID = COINBASE

    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"

    @staticmethod
    def _order_status(data):
        status = data['status']
        if data['status'] == 'done' and data['done_reason'] == 'canceled':
            status = PARTIAL
        elif data['status'] == 'done':
            status = FILLED
        elif data['status'] == 'open':
            status = OPEN
        elif data['status'] == 'pending':
            status = PENDING
        elif data['status'] == CANCELLED:
            status = CANCELLED

        if 'price' not in data:
            price = Decimal(data['executed_value']) / Decimal(data['filled_size'])
        else:
            price = Decimal(data['price'])

        return {
            'order_id': data['id'],
            'symbol': data['product_id'],
            'side': BUY if data['side'] == 'buy' else SELL,
            'order_type': LIMIT if data['type'] == 'limit' else MARKET,
            'price': price,
            'total': Decimal(data['size']),
            'executed': Decimal(data['filled_size']),
            'pending': Decimal(data['size']) - Decimal(data['filled_size']),
            'timestamp': pd.Timestamp(data['done_at']).timestamp() if 'done_at' in data else pd.Timestamp(data['created_at']).timestamp(),
            'order_status': status
        }

    def _generate_signature(self, endpoint: str, method: str, body=''):
        timestamp = str(time.time())
        message = ''.join([timestamp, method, endpoint, body])
        hmac_key = base64.b64decode(self.key_secret)
        signature = hmac.new(hmac_key, message.encode('ascii'), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'CB-ACCESS-KEY': self.key_id,  # The api key as a string.
            'CB-ACCESS-SIGN': signature_b64,  # The base64-encoded signature (see Signing a Message).
            'CB-ACCESS-TIMESTAMP': timestamp,  # A timestamp for your request.
            'CB-ACCESS-PASSPHRASE': self.key_passphrase,  # The passphrase you specified when creating the API key
            'Content-Type': 'Application/JSON',
        }

    def _request(self, method: str, endpoint: str, auth=False, body=None, retry=None, retry_wait=0):
        api = self.sandbox_api if self.sandbox else self.api

        @request_retry(self.ID, retry, retry_wait)
        def helper(verb, api, endpoint, body, auth):
            header = None
            if auth:
                header = self._generate_signature(endpoint, verb, body=json.dumps(body) if body else '')

            if method == "GET":
                return requests.get(f'{api}{endpoint}', headers=header)
            elif method == 'POST':
                return requests.post(f'{api}{endpoint}', json=body, headers=header)
            elif method == 'DELETE':
                return requests.delete(f'{api}{endpoint}', headers=header)

        return helper(method, api, endpoint, body, auth)

    def _date_to_trade(self, symbol: str, date: pd.Timestamp) -> int:
        """
        Coinbase uses trade ids to query historical trades, so
        need to search for the start date
        """
        upper = self._request('GET', f'/products/{symbol}/trades').json()[0]['trade_id']
        lower = 0
        bound = (upper - lower) // 2
        while True:
            r =  self._request('GET', f'/products/{symbol}/trades?after={bound}')
            if r.status_code == 429:
                time.sleep(10)
                continue
            elif r.status_code != 200:
                LOG.warning("Error %s: %s", r.status_code, r.text)
                time.sleep(60)
                continue
            data = r.json()
            data = list(reversed(data))
            if len(data) == 0:
                return bound
            if pd.Timestamp(data[0]['time']) <= date <= pd.Timestamp(data[-1]['time']):
                for idx in range(len(data)):
                    d = pd.Timestamp(data[idx]['time'])
                    if d >= date:
                        return data[idx]['trade_id']
            else:
                if date > pd.Timestamp(data[0]['time']):
                    lower = bound
                    bound = (upper + lower) // 2
                else:
                    upper = bound
                    bound = (upper + lower) // 2
            time.sleep(0.2)

    def _trade_normalize(self, symbol: str, data: dict) -> dict:
        return {
            'timestamp': timestamp_normalize(self.ID, data['time']),
            'pair': symbol,
            'id': data['trade_id'],
            'feed': self.ID,
            'side': SELL if data['side'] == 'buy' else BUY,
            'amount': data['size'],
            'price': data['price'],
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        if end and not start:
            start = '2014-12-01'
        if start:
            if not end:
                end = pd.Timestamp.utcnow()
            start_id = self._date_to_trade(symbol, pd.Timestamp(start, tzinfo=UTC))
            end_id = self._date_to_trade(symbol, pd.Timestamp(end, tzinfo=UTC))
            while True:
                limit = 100
                start_id += 100
                if start_id > end_id:
                    limit = 100 - (start_id - end_id)
                    start_id = end_id
                if limit > 0:
                    r =  self._request('GET', f'/products/{symbol}/trades?after={start_id}&limit={limit}', retry=retry, retry_wait=retry_wait)
                    if r.status_code == 429:
                        time.sleep(10)
                        continue
                    elif r.status_code != 200:
                        LOG.warning("Error %s: %s", r.status_code, r.text)
                        time.sleep(60)
                        continue
                    data = r.json()
                    try:
                        data = list(reversed(data))
                    except Exception:
                        LOG.warning("Error %s: %s", r.status_code, r.text)
                        sleep(60)
                        continue
                else:
                    break

                yield list(map(lambda x: self._trade_normalize(symbol, x), data))
                if start_id >= end_id:
                    break
        else:
            yield [self._trade_normalize(symbol, d) for d in self._request('GET', f"/products/{symbol}/trades", retry=retry, retry_wait=retry_wait).json()]

    def ticker(self, symbol: str, retry=None, retry_wait=10):
        data = self._request('GET', f'/products/{symbol}/ticker', retry=retry, retry_wait=retry_wait)
        self._handle_error(data, LOG)
        data = data.json()
        return {'pair': symbol,
                'feed': self.ID,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
               }

    def _book(self, symbol: str, level: int, retry, retry_wait):
        return self._request('GET', f'/products/{symbol}/book?level={level}', retry=retry, retry_wait=retry_wait).json()

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        data = self._book(symbol, 2, retry, retry_wait)
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

    def l3_book(self, symbol: str, retry=None, retry_wait=10):
        orders = self._book(symbol, 3, retry, retry_wait)
        ret = {BID: sd({}), ASK: sd({})}
        for side in (BID, ASK):
            for price, size, order_id in orders[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                if price in ret[side]:
                    ret[side][price][order_id] = size
                else:
                    ret[side][price] = {order_id: size}
        return ret

    def balances(self):
        resp = self._request('GET', "/accounts", auth=True)
        self._handle_error(resp, LOG)
        return {
            entry['currency']: {
                'total': Decimal(entry['balance']),
                'available': Decimal(entry['available'])
            }
            for entry in resp.json()
        }

    def orders(self):
        endpoint = "/orders"
        data = self._request("GET", endpoint, auth=True).json()
        return [Coinbase._order_status(order) for order in data]

    def order_status(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self._request("GET", endpoint, auth=True).json()
        return Coinbase._order_status(order)

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
        ot = normalize_trading_options(self.ID, order_type)
        if ot == MARKET and price:
            raise ValueError('Cannot specify price on a market order')
        if ot == LIMIT and not price:
            raise ValueError('Must specify price on a limit order')

        body = {
            'product_id': symbol,
            'side': 'buy' if BUY else SELL,
            'size': str(amount),
            'type': ot
        }

        if price:
            body['price'] = str(price)
        if client_order_id:
            body['client_oid'] = client_order_id
        if options:
            _ = [body.update(normalize_trading_options(self.ID, o)) for o in options]
        resp = self._request('POST', '/orders', auth=True, body=body)
        return Coinbase._order_status(resp.json())

    def cancel_order(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self.order_status(order_id)
        data = self._request("DELETE", endpoint, auth=True).json()
        if data[0] == order['order_id']:
            order['status'] = CANCELLED
            return order
        return data

    def trade_history(self, symbol: str, start=None, end=None):
        endpoint = f"/orders?product_id={symbol}&status=done"
        data = self._request("GET", endpoint, auth=True).json()
        return [
            {
                'order_id': order['id'],
                'trade_id': order['id'],
                'side': BUY if order['side'] == 'buy' else SELL,
                'price': Decimal(order['executed_value']) / Decimal(order['filled_size']),
                'amount': Decimal(order['filled_size']),
                'timestamp': pd.Timestamp(order['done_at']).timestamp(),
                'fee_amount': Decimal(order['fill_fees']),
                'fee_currency': symbol.split('-')[1]
            }
            for order in data
        ]
