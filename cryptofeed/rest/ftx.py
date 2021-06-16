'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import hmac
import logging
from time import sleep, time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, DELETE, GET, LIMIT, POST
from cryptofeed.defines import FTX as FTX_ID
from cryptofeed.defines import SELL
from cryptofeed.exchanges import FTX as FTXEx
from cryptofeed.rest.api import API, request_retry


LOG = logging.getLogger('rest')
RATE_LIMIT_SLEEP = 0.2


class FTX(API):
    ID = FTX_ID
    info = FTXEx()
    api = "https://ftx.com/api"
    session = requests.Session()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, GET, params=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _post(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, POST, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, DELETE, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _send_request(self, endpoint: str, http_method=GET, retry=None, retry_wait=0, auth=False, **kwargs):
        @request_retry(self.ID, retry, retry_wait)
        def helper():
            request = requests.Request(method=http_method, url=self.api + endpoint, **kwargs)
            if auth:
                self._sign_request(request)
            r = self.session.send(request.prepare())
            self._handle_error(r, LOG)
            return r.json()
        return helper()

    def _sign_request(self, request: requests.Request) -> None:
        ts = int(time() * 1000)
        prepared = request.prepare()
        signature_payload = f'{ts}{prepared.method}{prepared.path_url}'.encode()
        if prepared.body:
            signature_payload += prepared.body
        signature = hmac.new(self.config.key_secret.encode(), signature_payload, 'sha256').hexdigest()
        request.headers['FTX-KEY'] = self.config.key_id
        request.headers['FTX-SIGN'] = signature
        request.headers['FTX-TS'] = str(ts)

    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/markets/{sym}", retry=retry, retry_wait=retry_wait)

        return {'symbol': symbol,
                'feed': self.ID,
                'bid': data['result']['bid'],
                'ask': data['result']['ask']
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/markets/{sym}/orderbook", params={'depth': 100}, retry=retry, retry_wait=retry_wait)
        return {
            BID: sd({
                u[0]: u[1]
                for u in data['result']['bids']
            }),
            ASK: sd({
                u[0]: u[1]
                for u in data['result']['asks']
            })
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.info.std_symbol_to_exchange_symbolself.info.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

    def funding(self, symbol: str, start_date=None, end_date=None, retry=None, retry_wait=10):
        start = None
        end = None

        if end_date and not start_date:
            start_date = '2019-01-01'

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = API._timestamp(start_date)
            end = API._timestamp(end_date)

            start = int(start.timestamp())
            end = int(end.timestamp())

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}/funding_rates?future={symbol}&start_time={start}&end_time={end}")
            else:
                return requests.get(f"{self.api}/funding_rates?symbol={symbol}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.ID, start, end)
            else:
                end = int(API._timestamp(data[-1]["time"]).timestamp()) + 1

            data = [self._funding_normalization(x, symbol) for x in data]
            return data

    def place_order(self, symbol: str, side: str, amount: Decimal, price: Decimal, order_type: str = LIMIT,
                    reduce_only: bool = False, ioc: bool = False, post_only: bool = False, client_id: str = None) -> dict:
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        return self._post('/orders', params={
            'market': sym,
            'side': side,
            'price': price,
            'size': amount,
            'type': order_type,
            'reduceOnly': reduce_only,
            'ioc': ioc,
            'postOnly': post_only,
            'clientId': client_id,
        }, auth=True)

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f'/orders/{order_id}', auth=True)

    def orders(self, symbol: str) -> List[dict]:
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        return self._get('/orders', params={'market': sym}, auth=True)

    def positions(self, show_avg_price: bool = False) -> List[dict]:
        return self._get('/positions', params={'showAvgPrice': show_avg_price}, auth=True)

    @staticmethod
    def _dedupe(data, last):
        if len(last) == 0:
            return data

        ids = set([data['id'] for data in last])
        ret = []

        for d in data:
            if d['id'] in ids:
                continue
            ids.add(d['id'])
            ret.append(d)

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date, retry, retry_wait):
        last = []
        start = None
        end = None

        if end_date and not start_date:
            start_date = '2019-01-01'

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = API._timestamp(start_date)
            end = API._timestamp(end_date)

            start = int(start.timestamp())
            end = int(end.timestamp())

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}/markets/{symbol}/trades?limit=100&start_time={start}&end_time={end}")
            else:
                return requests.get(f"{self.api}/markets/{symbol}/trades")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.ID, start, end)
            else:
                end = int(API._timestamp(data[-1]["time"]).timestamp()) + 1

            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = [self._trade_normalization(x, symbol) for x in data]
            yield data

            if len(orig_data) < 100:
                break

    def _trade_normalization(self, trade: dict, symbol: str) -> dict:
        return {
            'timestamp': API._timestamp(trade['time']).timestamp(),
            'symbol': symbol,
            'id': trade['id'],
            'feed': self.ID,
            'side': SELL if trade['side'] == 'sell' else BUY,
            'amount': trade['size'],
            'price': trade['price']
        }

    def _funding_normalization(self, funding: dict, symbol: str) -> dict:
        return {
            'timestamp': API._timestamp(funding['time']).timestamp(),
            'symbol': funding['future'],
            'feed': self.ID,
            'rate': funding['rate']
        }
