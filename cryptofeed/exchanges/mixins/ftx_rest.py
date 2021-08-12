'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import hmac
import logging
import requests
from time import time
from typing import Any, Dict, List, Optional
import urllib.parse

from yapic import json
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, DELETE, FUNDING, GET, L2_BOOK, LIMIT, POST, TICKER, TRADES
from cryptofeed.defines import SELL
from cryptofeed.exchange import RestExchange


LOG = logging.getLogger('cryptofeed.rest')


class FTXRestMixin(RestExchange):
    api = "https://ftx.com/api"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, FUNDING
    )

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, GET, params=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _post(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, POST, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None, retry=None, retry_wait=0, auth=False):
        return self._send_request(endpoint, DELETE, json=params, retry=retry, retry_wait=retry_wait, auth=auth)

    def _send_request(self, endpoint: str, http_method=GET, retry=None, retry_wait=0, auth=False, **kwargs):
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

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/markets/{sym}", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)['result']

        return {'symbol': symbol,
                'feed': self.id,
                'bid': data['bid'],
                'ask': data['ask']
                }

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/markets/{sym}/orderbook?depth=100", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)['result']

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

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        last = []
        start, end = self._interval_normalize(start, end)

        while True:
            endpoint = f"{self.api}/markets/{symbol}/trades"
            if start and end:
                endpoint = f"{self.api}/markets/{symbol}/trades?start_time={start}&end_time={end}"

            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)['result']

            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = [self._trade_normalization(x, symbol) for x in data]
            yield data

            if len(orig_data) < 5000:
                break
            end = int(data[-1]['timestamp'])
            await asyncio.sleep(1 / self.request_limit)

    async def funding(self, symbol: str, retry_count=1, retry_delay=10):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        endpoint = f"{self.api}/funding_rates?future={sym}"
        r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(r, parse_float=Decimal)['result']
        data = [self._funding_normalization(x) for x in data]
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

    def _funding_normalization(self, funding: dict) -> dict:
        return {
            'symbol': self.exchange_symbol_to_std_symbol(funding['future']),
            'feed': self.id,
            'rate': funding['rate'],
            'timestamp': funding['time'].timestamp(),
        }
