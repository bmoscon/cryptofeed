'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse
import logging

from sortedcontainers import SortedDict as sd
import requests
import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import BITMEX, SELL, BUY, BID, ASK
from cryptofeed.standards import timestamp_normalize


API_MAX = 500
API_REFRESH = 300

LOG = logging.getLogger('rest')


class Bitmex(API):
    ID = BITMEX
    api = 'https://www.bitmex.com'

    def _generate_signature(self, verb: str, url: str, data='') -> dict:
        """
        verb: GET/POST/PUT
        url: api endpoint
        data: body (if present)
        """
        expires = int(round(time.time()) + 30)

        parsedURL = urlparse(url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query

        if isinstance(data, (bytes, bytearray)):
            data = data.decode('utf8')

        message = verb + path + str(expires) + data

        signature = hmac.new(bytes(self.key_secret, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
        return {
            "api-expires": str(expires),
            "api-key": self.key_id,
            "api-signature": signature
        }

    def _get(self, ep, symbol, start_date, end_date, retry, retry_wait, freq='6H'):
        dates = [None]
        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            dates = pd.interval_range(API._timestamp(start_date), API._timestamp(end_date), freq=freq).tolist()
            if len(dates) == 0:
                dates.append(pd.Interval(left=API._timestamp(start_date), right=API._timestamp(end_date)))
            elif dates[-1].right < API._timestamp(end_date):
                dates.append(pd.Interval(dates[-1].right, API._timestamp(end_date)))

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, start_date, end_date):
            if start_date and end_date:
                endpoint = f'/api/v1/{ep}?symbol={symbol}&count={API_MAX}&reverse=false&start={start}&startTime={start_date}&endTime={end_date}'
            else:
                endpoint = f'/api/v1/{ep}?symbol={symbol}&reverse=true'
            header = {}
            if self.key_id and self.key_secret:
                header = self._generate_signature("GET", endpoint)
            header['Accept'] = 'application/json'
            return requests.get('{}{}'.format(self.api, endpoint), headers=header)

        for interval in dates:
            start = 0
            if interval is not None:
                end = interval.right
                end -= pd.Timedelta(nanoseconds=1)

                start_date = str(interval.left).replace(" ", "T") + "Z"
                end_date = str(end).replace(" ", "T") + "Z"

            while True:
                r = helper(start, start_date, end_date)

                if r.status_code in {502, 504}:
                    LOG.warning("%s: %d for URL %s - %s", self.ID, r.status_code, r.url, r.text)
                    sleep(retry_wait)
                    continue
                elif r.status_code == 429:
                    sleep(API_REFRESH)
                    continue
                elif r.status_code != 200:
                    self._handle_error(r, LOG)

                limit = int(r.headers['X-RateLimit-Remaining'])
                data = r.json()

                yield data

                if len(data) != API_MAX:
                    break

                if limit < 1:
                    sleep(API_REFRESH)

                start += len(data)

    def _trade_normalization(self, trade: dict) -> dict:
        return {
            'timestamp': timestamp_normalize(self.ID, trade['timestamp']),
            'pair': trade['symbol'],
            'id': trade['trdMatchID'],
            'feed': self.ID,
            'side': BUY if trade['side'] == 'Buy' else SELL,
            'amount': trade['size'],
            'price': trade['price']
        }

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        """
        data format

        {
            'timestamp': '2018-01-01T23:59:59.907Z',
            'symbol': 'XBTUSD',
            'side': 'Buy',
            'size': 1900,
            'price': 13477,
            'tickDirection': 'ZeroPlusTick',
            'trdMatchID': '14fcc8d7-d056-768d-3c46-1fdf98728343',
            'grossValue': 14098000,
            'homeNotional': 0.14098,
            'foreignNotional': 1900
        }
        """
        for data in self._get('trade', symbol, start, end, retry, retry_wait):
            yield list(map(self._trade_normalization, data))

    def _funding_normalization(self, funding: dict) -> dict:
        return {
            'timestamp': funding['timestamp'],
            'pair': funding['symbol'],
            'feed': self.ID,
            'interval': funding['fundingInterval'],
            'rate': funding['fundingRate'],
            'rate_daily': funding['fundingRateDaily']
        }

    def funding(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        """
        {
            'timestamp': '2017-01-05T12:00:00.000Z',
            'symbol': 'XBTUSD',
            'fundingInterval': '2000-01-01T08:00:00.000Z',
            'fundingRate': 0.00375,
            'fundingRateDaily': 0.01125
        }
        """
        for data in self._get('funding', symbol, start, end, retry, retry_wait, freq='2W'):
            yield list(map(self._funding_normalization, data))

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        ret = {symbol: {BID: sd(), ASK: sd()}}
        data = next(self._get('orderBook/L2', symbol, None, None, retry, retry_wait))
        for update in data:
            side = ASK if update['side'] == 'Sell' else BID
            ret[symbol][side][update['price']] = update['size']
        return ret
