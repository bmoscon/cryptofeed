import time
import json
import hashlib
import hmac
import requests
import base64
from time import sleep
from datetime import datetime as dt
import logging

import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import COINBASE, BUY, SELL
from cryptofeed.standards import pair_std_to_exchange


REQUEST_LIMIT = 10
LOG = logging.getLogger('rest')


# API Docs https://docs.gdax.com/
class Coinbase(API):
    ID = COINBASE

    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"

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
                header = self._generate_signature(endpoint, verb, body=json.dumps(body) if body else None)

            if method == "GET":
                return requests.get(f'{api}{endpoint}', headers=header)

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
            try:
                data = list(reversed(data))
            except:
                LOG.warning("Error %s: %s", r.status_code, r.text)
                sleep(60)
                continue
            if pd.Timestamp(data[0]['time'].replace("Z", '')) <= date <= pd.Timestamp(data[-1]['time'].replace("Z", '')):
                for idx in range(len(data)):
                    d = pd.Timestamp(data[idx]['time'].replace("Z", ''))
                    if d >= date:
                        return data[idx]['trade_id']
            else:
                if date > pd.Timestamp(data[0]['time'].replace("Z", "")):
                    lower = bound
                    bound = (upper + lower) // 2
                else:
                    upper = bound
                    bound = (upper + lower) // 2
            time.sleep(0.2)

    def _trade_normalize(self, symbol: str, data: dict) -> dict:
        return {
            'timestamp': data['time'],
            'pair': symbol,
            'id': data['trade_id'],
            'feed': self.ID,
            'side': SELL if data['side'] == 'buy' else BUY,
            'amount': data['size'],
            'price': data['price'],
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        if start:
            if not end:
                end = pd.Timestamp.utcnow()
            start_id = self._date_to_trade(symbol, pd.Timestamp(start))
            end_id = self._date_to_trade(symbol, pd.Timestamp(end))
            while True:
                limit = 100
                start_id += 100
                if start_id > end_id:
                    limit = 100 - (start_id - end_id)
                    start_id = end_id
                if limit > 0:
                    r =  self._request('GET', f'/products/{symbol}/trades?after={start_id}&limit={limit}')
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
                    except:
                        LOG.warning("Error %s: %s", r.status_code, r.text)
                        sleep(60)
                        continue
                else:
                    break

                yield list(map(lambda x: self._trade_normalize(symbol, x), data))
                if start_id >= end_id:
                    break
        else:
            yield [self._trade_normalize(symbol, d) for d in self._request('GET', f"/product/{symbol}/trades")]
