'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests
import hmac
from urllib import parse
from requests import Request
import logging
from time import sleep, time

import pandas as pd
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import FTX as FTX_ID, SELL, BUY, BID, ASK
from cryptofeed.standards import pair_std_to_exchange


LOG = logging.getLogger('rest')
RATE_LIMIT_SLEEP = 0.2


class FTX(API):
    ID = FTX_ID

    api = "https://ftx.com/api"

    def __init__(self, config, sandbox=False, **kwargs):
        super().__init__(config, sandbox, **kwargs)
        if 'subaccount' in kwargs:
            self.subaccount = kwargs['subaccount']
        else:
            self.subaccount = None

    def _get(self, command: str, params=None, retry=None, retry_wait=0):
        url = f"{self.api}{command}"

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            resp = requests.get(url, params={} if not params else params)
            self._handle_error(resp, LOG)
            return resp.json()
        return helper()

    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get(f"/markets/{sym}", retry=retry, retry_wait=retry_wait)

        return {'pair': symbol,
                'feed': self.ID,
                'bid': data['result']['bid'],
                'ask': data['result']['ask']
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get(f"/markets/{sym}/orderbook", {'depth': 100}, retry=retry, retry_wait=retry_wait)
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
        symbol = pair_std_to_exchange(symbol, self.ID)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

    def deposits(self):
        h = self._sign(f"{self.api}/wallet/deposits")
        r = requests.get(f"{self.api}/wallet/deposits", headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            for deposit in data:
                deposit['time'] = API._timestamp(deposit['time']).timestamp() * 1000
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data

    def withdrawals(self):
        h = self._sign(f"{self.api}/wallet/withdrawals")
        r = requests.get(f"{self.api}/wallet/withdrawals", headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            for withdrawal in data:
                withdrawal['time'] = API._timestamp(withdrawal['time']).timestamp() * 1000
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data

    def all_balances(self):
        h = self._sign(f"{self.api}/wallet/all_balances")
        r = requests.get(f"{self.api}/wallet/all_balances", headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data


    def positions(self):
        h = self._sign(f"{self.api}/positions")
        r = requests.get(f"{self.api}/positions", headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data

    def funding_payments(self, symbol=None, start_date=None, end_date=None):
        if not start_date:
            start_date = '2019-01-01'

        if not end_date:
            end_date = pd.Timestamp.utcnow()

        start = API._timestamp(start_date)
        end = API._timestamp(end_date)

        start = int(start.timestamp())
        end = int(end.timestamp())

        if symbol == None:
            url = f"{self.api}/funding_payments?start_time={start}&end_time={end}"
        else:
            url = f"{self.api}/funding_payments?symbol={symbol}&start_time={start}&end_time={end}"

        h = self._sign(url)
        r = requests.get(url, headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            for payment in data:
                payment['time'] = API._timestamp(payment['time']).timestamp() * 1000
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data

    def fills(self, symbol=None, start_date=None, end_date=None):
        start = None
        end = None

        if not start_date:
            start_date = '2019-01-01'

        if not end_date:
            end_date = pd.Timestamp.utcnow()

        start = API._timestamp(start_date)
        end = API._timestamp(end_date)

        start = int(start.timestamp())
        end = int(end.timestamp())

        if symbol == None:
            url = f"{self.api}/fills?start_time={start}&end_time={end}"
        else:
            url = f"{self.api}/fills?symbol={symbol}&start_time={start}&end_time={end}"

        h = self._sign(url)
        r = requests.get(url, headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            for fills in data:
                fills['time'] = API._timestamp(fills['time']).timestamp() * 1000
            if data == []:
                LOG.warning("%s: No data", self.ID)

            if len(data) == 5000:
                end_date = data[4999]['time'] - 1
                data += self.fills(end_date=end_date)
            return data

    def subaccounts(self):
        h = self._sign(f"{self.api}/subaccounts")
        r = requests.get(f"{self.api}/subaccounts", headers=h.headers)

        while True:
            if r.status_code == 429:
                sleep(RATE_LIMIT_SLEEP)
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(10)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()['result']
            if data == []:
                LOG.warning("%s: No data", self.ID)

            return data

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
            if not data:
                LOG.warning("%s: No data for range %d - %d", self.ID, start, end)
            else:
                end = int(API._timestamp(data[-1]["time"]).timestamp()) + 1

            orig_data = list(data)
            # data = self._dedupe(data, last)
            # last = list(orig_data)

            data = [self._funding_normalization(x, symbol) for x in data]
            return data

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
            'timestamp': API._timestamp(trade['time']).timestamp() * 1000,
            'pair': symbol,
            'id': trade['id'],
            'feed': self.ID,
            'side': SELL if trade['side'] == 'sell' else BUY,
            'amount': trade['size'],
            'price': trade['price']
        }

    def _funding_normalization(self, funding: dict, symbol: str) -> dict:
        ts = pd.to_datetime(funding['time'], format="%Y-%m-%dT%H:%M:%S%z")
        return {
            'timestamp': API._timestamp(funding['time']).timestamp() * 1000,
            'pair': funding['future'],
            'feed': self.ID,
            'rate': funding['rate']
        }

    def _sign(self, url):
        ts = int(time() * 1000)
        request = Request('GET', url)
        prepared = request.prepare()
        signature_payload = f'{ts}{prepared.method}{prepared.path_url}'
        if prepared.body:
            signature_payload += prepared.body
        signature_payload = signature_payload.encode()
        signature = hmac.new(self.key_secret.encode(), signature_payload, 'sha256').hexdigest()

        request.headers['FTX-KEY'] = self.key_id
        request.headers['FTX-SIGN'] = signature
        request.headers['FTX-TS'] = str(ts)
        if self.subaccount is not None:
            request.headers['FTX-SUBACCOUNT'] = parse.quote(self.subaccount)
        return request


if __name__ == "__main__":
    e = FTX(None, account='ftx_coen')
    e.fills()
