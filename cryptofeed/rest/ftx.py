'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import requests
import logging
from time import sleep

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

    def _dedupe(self, data, last):
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
            'pair': symbol,
            'id': trade['id'],
            'feed': self.ID,
            'side': SELL if trade['side'] == 'sell' else BUY,
            'amount': trade['size'],
            'price': trade['price']
        }
