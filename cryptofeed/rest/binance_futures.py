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

import pandas as pd
import requests
from yapic import json

from cryptofeed.exchanges import BinanceFutures, BinanceDelivery
from cryptofeed.defines import BINANCE_FUTURES, BUY, SELL, BINANCE_DELIVERY
from cryptofeed.rest.api import API, request_retry
from cryptofeed.standards import timestamp_normalize

REQUEST_LIMIT = 1000
RATE_LIMIT_SLEEP = 3
LOG = logging.getLogger('rest')


class BinanceDelivery(API):
    ID = BINANCE_DELIVERY
    api = "https://dapi.binance.com/dapi/v1/"
    info = BinanceDelivery()

    def _get(self, endpoint, retry, retry_wait):
        @request_retry(self.ID, retry, retry_wait)
        def helper():
            r = requests.get(f"{self.api}{endpoint}")
            self._handle_error(r, LOG)
            return r.json()

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
            'timestamp': timestamp_normalize(self.ID, trade['T']),
            'symbol': self.info.exchange_symbol_to_std_symbol(symbol),
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
                return requests.get(f"{self.api}aggTrades?symbol={symbol}&limit={REQUEST_LIMIT}&startTime={start}&endTime={end}")
            else:
                return requests.get(f"{self.api}aggTrades?symbol={symbol}")

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
        symbol = self.info.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data


class BinanceFutures(API):
    ID = BINANCE_FUTURES
    api = "https://fapi.binance.com/fapi/v1/"
    info = BinanceFutures()

    def _get(self, endpoint, retry, retry_wait):
        @request_retry(self.ID, retry, retry_wait)
        def helper():
            r = requests.get(f"{self.api}{endpoint}")
            self._handle_error(r, LOG)
            return r.json()

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
            'timestamp': timestamp_normalize(self.ID, trade['T']),
            'symbol': self.info.exchange_symbol_to_std_symbol(symbol),
            'id': trade['a'],
            'feed': self.ID,
            'side': BUY if trade['m'] else SELL,
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
                return requests.get(
                    f"{self.api}aggTrades?symbol={symbol}&limit={REQUEST_LIMIT}&startTime={start}&endTime={end}")
            else:
                return requests.get(f"{self.api}aggTrades?symbol={symbol}")

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
                    LOG.warning(
                        "%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d",
                        self.ID, start)
                    start += 1
                else:
                    start = data[-1]['T']

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(data) < REQUEST_LIMIT:
                break

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.info.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data
