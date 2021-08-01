'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import hmac
from time import sleep, time
from typing import Any, Dict, List, Optional
from datetime import datetime as dt

from yapic import json
import requests
from sortedcontainers.sorteddict import SortedDict as sd
import urllib.parse

from cryptofeed.defines import BID, ASK, BUY, CANCEL_ORDER, DELETE, FUNDING, GET, L2_BOOK, LIMIT, ORDER_INFO, ORDER_STATUS, PLACE_ORDER, POST, TICKER, TRADES, TRADE_HISTORY
from cryptofeed.defines import SELL
from cryptofeed.exchange import RestExchange
from cryptofeed.connection import request_retry


LOG = logging.getLogger('cryptofeed.rest')


class FTXRestMixin(RestExchange):
    session = requests.Session()
    api = "https://ftx.com/api"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, FUNDING, ORDER_INFO, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, TRADE_HISTORY
    )

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, GET, params=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _post(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, POST, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, DELETE, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _send_request(self, endpoint: str, http_method=GET, retry=None, retry_wait=0, auth=False, **kwargs):
        @request_retry(self.id, retry, retry_wait)
        def helper():
            request = requests.Request(method=http_method, url=self.api + endpoint, **kwargs)
            if auth:
                self._sign_request(request)
            r = self.session.send(request.prepare())
            self._handle_error(r)
            return json.loads(r.text, parse_float=Decimal)['result']
        return helper()

    def _sign_request(self, request: requests.Request) -> None:
        ts = int(time() * 1000)
        prepared = request.prepare()
        signature_payload = f'{ts}{prepared.method}{prepared.path_url}'.encode()
        if prepared.body:
            signature_payload += prepared.body
        signature = hmac.new(self.key_secret.encode(), signature_payload, 'sha256').hexdigest()
        request.headers['FTX-KEY'] = self.key_id
        request.headers['FTX-SIGN'] = signature
        request.headers['FTX-TS'] = str(ts)
        if self.subaccount:
            request.headers['FTX-SUBACCOUNT'] = urllib.parse.quote(self.subaccount)

    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/markets/{sym}", retry=retry, retry_wait=retry_wait)

        return {'symbol': symbol,
                'feed': self.id,
                'bid': data['bid'],
                'ask': data['ask']
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/markets/{sym}/orderbook", params={'depth': 100}, retry=retry, retry_wait=retry_wait)
        return {
            BID: sd({
                u[0]: u[1]
                for u in data['bids']
            }),
            ASK: sd({
                u[0]: u[1]
                for u in data['asks']
            })
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

    def funding(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        sym = self.std_symbol_to_exchange_symbol(symbol)

        if start or end:
            if end and not start:
                start = '2019-01-01'
            elif start and not end:
                end = dt.now().timestamp()
            start = int(self._datetime_normalize(start))
            end = int(self._datetime_normalize(end))

        @request_retry(self.id, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}/funding_rates?future={sym}&start_time={start}&end_time={end}")
            else:
                return requests.get(f"{self.api}/funding_rates?symbol={sym}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(1 / self.request_limit)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(1 / self.request_limit)

            data = json.loads(r.text, parse_float=Decimal)['result']
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.id, start, end)
            else:
                end = int(data[-1]["time"].timestamp() + 1)

            data = [self._funding_normalization(x, symbol) for x in data]
            return data

    def place_order(self, symbol: str, side: str, amount: Decimal, price: Decimal, order_type: str = LIMIT,
                    reduce_only: bool = False, ioc: bool = False, post_only: bool = False, client_id: str = None) -> dict:
        sym = self.std_symbol_to_exchange_symbol(symbol)
        return self._post('/orders', params={
            'market': sym,
            'side': side,
            'price': str(price),
            'size': str(amount),
            'type': order_type,
            'reduceOnly': reduce_only,
            'ioc': ioc,
            'postOnly': post_only,
            'clientId': client_id,
        }, auth=True)

    def cancel_order(self, order_id: str) -> dict:
        return self._delete(f'/orders/{order_id}', auth=True)

    def orders(self, symbol: str) -> List[dict]:
        sym = self.std_symbol_to_exchange_symbol(symbol)
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

    def _get_trades_hist(self, symbol, start, end, retry, retry_wait):
        last = []

        if start or end:
            if end and not start:
                start = '2019-01-01'
            elif start and not end:
                end = dt.now().timestamp()
            start = int(self._datetime_normalize(start))
            end = int(self._datetime_normalize(end))

        @request_retry(self.id, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}/markets/{symbol}/trades?start_time={start}&end_time={end}")
            else:
                return requests.get(f"{self.api}/markets/{symbol}/trades")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(30)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(1 / self.request_limit)

            data = json.loads(r.text, parse_float=Decimal)['result']
            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = [self._trade_normalization(x, symbol) for x in data]
            yield data

            if len(orig_data) < 5000:
                break
            end = int(data[-1]['timestamp'])

    def _trade_normalization(self, trade: dict, symbol: str) -> dict:
        return {
            'timestamp': trade['time'].timestamp(),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['id'],
            'feed': self.id,
            'side': SELL if trade['side'] == 'sell' else BUY,
            'amount': trade['size'],
            'price': trade['price']
        }

    def _funding_normalization(self, funding: dict, symbol: str) -> dict:
        return {
            'timestamp': funding['time'].timestamp(),
            'symbol': self.exchange_symbol_to_std_symbol(funding['future']),
            'feed': self.id,
            'rate': funding['rate']
        }
