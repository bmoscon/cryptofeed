'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import hashlib
import hmac
import logging
import time
from time import sleep
from datetime import datetime as dt

import requests
from yapic import json

from cryptofeed.defines import BUY, SELL, TRADES
from cryptofeed.connection import request_retry
from cryptofeed.exchange import RestExchange


LOG = logging.getLogger('cryptofeed.rest')


class BinanceDeliveryRestMixin(RestExchange):
    api = "https://dapi.binance.com/dapi/v1/"
    rest_channels = (
        TRADES
    )

    def _get(self, endpoint, retry, retry_wait):
        @request_retry(self.id, retry, retry_wait)
        def helper():
            r = requests.get(f"{self.api}{endpoint}")
            self._handle_error(r)
            return json.loads(r.text, parse_float=Decimal)

        return helper()

    def _nonce(self):
        return str(int(round(time.time() * 1000)))

    def _generate_signature(self, url: str, body=json.dumps({})):
        nonce = self._nonce()
        signature = "/api/" + url + nonce + body
        h = hmac.new(self.config.key_secret.encode('utf8'), signature.encode('utf8'), hashlib.sha384)
        signature = h.hexdigest()

        return {
            "X-MBX-APIKEY": self.config.key_id,
            "signature": signature,
            "content-type": "application/json"
        }

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        ret = {
            'timestamp': self.timestamp_normalize(trade['T']),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['a'],
            'feed': self.id,
            'side': BUY if trade['m'] is True else SELL,
            'amount': abs(Decimal(trade['q'])),
            'price': Decimal(trade['p']),
        }

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = dt.now().timestamp()
            start = self._datetime_normalize(start_date)
            end = self._datetime_normalize(end_date)

            start = int(start * 1000)
            end = int(end * 1000)

        @request_retry(self.id, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}aggTrades?symbol={symbol}&limit=1000&startTime={start}&endTime={end}")
            else:
                return requests.get(f"{self.api}aggTrades?symbol={symbol}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(1 / self.request_limit)

            data = json.loads(r.text, parse_float=Decimal)
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.id, start, end)
            else:
                if data[-1]['T'] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.id, start)
                    start += 1
                else:
                    start = data[-1]['T']

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(data) < 1000:
                break

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data


class BinanceFuturesRestMixin(RestExchange):
    api = "https://fapi.binance.com/fapi/v1/"
    rest_channels = (
        TRADES
    )

    def _get(self, endpoint, retry, retry_wait):
        @request_retry(self.id, retry, retry_wait)
        def helper():
            r = requests.get(f"{self.api}{endpoint}")
            self._handle_error(r)
            return json.loads(r.text, parse_float=Decimal)

        return helper()

    def _nonce(self):
        return str(int(round(time.time() * 1000)))

    def _generate_signature(self, url: str, body=json.dumps({})):
        nonce = self._nonce()
        signature = "/api/" + url + nonce + body
        h = hmac.new(self.config.key_secret.encode('utf8'), signature.encode('utf8'), hashlib.sha384)
        signature = h.hexdigest()

        return {
            "X-MBX-APIKEY": self.config.key_id,
            "signature": signature,
            "content-type": "application/json"
        }

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        ret = {
            'timestamp': self.timestamp_normalize(trade['T']),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['a'],
            'feed': self.id,
            'side': BUY if trade['m'] else SELL,
            'amount': abs(Decimal(trade['q'])),
            'price': Decimal(trade['p']),
        }

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = dt.now().timestamp()
            start = self._datetime_normalize(start_date)
            end = self._datetime_normalize(end_date)

            start = int(start * 1000)
            end = int(end * 1000)

        @request_retry(self.id, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(
                    f"{self.api}aggTrades?symbol={symbol}&limit=1000&startTime={start}&endTime={end}")
            else:
                return requests.get(f"{self.api}aggTrades?symbol={symbol}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(1 / self.request_limit)

            data = json.loads(r.text, parse_float=Decimal)
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.id, start, end)
            else:
                if data[-1]['T'] == start:
                    LOG.warning(
                        "%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d",
                        self.id, start)
                    start += 1
                else:
                    start = data[-1]['T']

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(data) < 1000:
                break

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data
