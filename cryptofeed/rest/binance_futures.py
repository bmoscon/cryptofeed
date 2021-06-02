'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import logging
import time
from time import sleep
from urllib.parse import urlencode

import pandas as pd
import requests
from yapic import json

from cryptofeed.defines import BINANCE, BINANCE_FUTURES, BUY, SELL, BINANCE_DELIVERY
from cryptofeed.rest.api import API, request_retry
from cryptofeed.standards import symbol_exchange_to_std, symbol_std_to_exchange, timestamp_normalize

REQUEST_LIMIT = 1000
RATE_LIMIT_SLEEP = 3
LOG = logging.getLogger('rest')


class Binance(API):
    ID = BINANCE
    base_url = 'https://api.binance.com'
    endpoint_url = '/api/v3/'

    def _send_request(self, endpoint, retry, retry_wait, endpoint_url=None, http_method='GET', auth=False, payload={}):
        def dispatch_request(http_method):
            session = requests.Session()
            session.headers.update({
                "X-MBX-APIKEY": self.config.key_id,
                # "signature": signature,
            })
            return {
                'GET': session.get,
                'DELETE': session.delete,
                'PUT': session.put,
                'POST': session.post,
            }.get(http_method, 'GET')
        
        @request_retry(self.ID, retry, retry_wait)
        def helper(endpoint_url, http_method, auth, payload):
            query_string = urlencode(payload)
            if auth:
                if query_string:
                    query_string = "{}&timestamp={}".format(query_string, self._nonce())
                else:
                    query_string = 'timestamp={}'.format(self._nonce())
            
            url = f"{self.base_url}{endpoint_url}{endpoint}?{query_string}"
            if auth:
                signature = self._generate_signature(query_string)
                url += f'&signature={signature}'
            
            params = {'url': url, 'params': {}}
            r = dispatch_request(http_method)(**params)
            self._handle_error(r, LOG)
            return r.json()
        return helper(self.endpoint_url if endpoint_url is None else endpoint_url, http_method, auth, payload)

    def _nonce(self):
        return str(int(time.time() * 1000))

    def _generate_signature(self, query_string: str):
        print("api key", self.config.key_id)
        h = hmac.new(self.config.key_secret.encode('utf8'), query_string.encode('utf8'), hashlib.sha256)
        return h.hexdigest()

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        ret = {
            'timestamp': timestamp_normalize(self.ID, trade['T']),
            'symbol': symbol_exchange_to_std(symbol),
            'id': trade['a'],
            'feed': self.ID,
            'side': BUY if trade['m'] is True else SELL,
            'amount': abs(float(trade['q'])),
            'price': float(trade['p']),
        }

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = API._timestamp(start_date)
            end = API._timestamp(end_date) - pd.Timedelta(nanoseconds=1)

            start = int(start.timestamp() * 1000)
            end = int(end.timestamp() * 1000)

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.base_url}{self.endpoint_url}aggTrades?symbol={symbol}&limit={REQUEST_LIMIT}&startTime={start}&endTime={end}")
            else:
                return requests.get(f"{self.base_url}{self.endpoint_url}aggTrades?symbol={symbol}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.ID, start, end)
            else:
                if data[-1]['T'] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.ID, start)
                    start += 1
                else:
                    start = data[-1]['T']

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(data) < REQUEST_LIMIT:
                break

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = symbol_std_to_exchange(symbol, self.ID)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

class BinanceDelivery(Binance):
    ID = BINANCE_DELIVERY
    base_url = 'https://dapi.binance.com'
    endpoint_url = '/dapi/v1/'

class BinanceFutures(Binance):
    ID = BINANCE_FUTURES
    base_url = 'https://fapi.binance.com'
    endpoint_url = '/fapi/v1/'
