from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse

import requests
import pandas as pd

from cryptofeed.rest.api import API
from cryptofeed.feeds import BITMEX


API_MAX = 500
API_REFRESH = 300


class Bitmex(API):
    ID = BITMEX
    api = 'https://www.bitmex.com'

    def _generate_signature(self, verb: str, url: str, data='') -> dict:
        """
        verb: GET/POST/PUT
        url: api endpoint
        data: body (if present)
        """
        expires = int(round(time.time()) + 5)

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

    def _get(self, ep, symbol, start_date, end_date, freq='6H'):
        dates = pd.interval_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq=freq).tolist()
        if dates[-1].right < pd.Timestamp(end_date):
            dates.append(pd.Interval(dates[-1].right, pd.Timestamp(end_date)))

        for interval in dates:
            start = 0

            end = interval.right
            end -= pd.Timedelta(nanoseconds=1)

            start_date = str(interval.left).replace(" ", "T") + "Z"
            end_date = str(end).replace(" ", "T") + "Z"

            while True:
                endpoint = '/api/v1/{}?symbol={}&count={}&reverse=false&start={}&startTime={}&endTime={}'.format(ep, symbol, API_MAX, start, start_date, end_date)
                header = {}
                if self.key_id and self.key_secret:
                    header = self._generate_signature("GET", endpoint)
                header['Accept'] = 'application/json'
                r = requests.get('{}{}'.format(self.api, endpoint), headers=header)
                try:
                    limit = int(r.headers['X-RateLimit-Remaining'])
                    if r.status_code == 429:
                        sleep(API_REFRESH)
                        continue
                    if r.status_code != 200:
                        r.raise_for_status()
                except:
                    print(r.text)
                    print(r.headers)
                    raise
                data = r.json()

                yield data

                if len(data) != API_MAX:
                    break

                if limit < 1:
                    sleep(API_REFRESH)

                start += len(data)

    def _trade_normalization(self, trade: dict) -> dict:
        return {
            'timestamp': trade['timestamp'],
            'pair': trade['symbol'],
            'id': trade['trdMatchID'],
            'feed': self.ID,
            'side': trade['side'],
            'amount': trade['size'],
            'price': trade['price']
        }

    def trades(self, symbol, start=None, end=None):
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
        if start and end:
            for data in self._get('trade', symbol, start, end):
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

    def funding(self, symbol, start=None, end=None):
        """
        {
            'timestamp': '2017-01-05T12:00:00.000Z',
            'symbol': 'XBTUSD',
            'fundingInterval': '2000-01-01T08:00:00.000Z',
            'fundingRate': 0.00375,
            'fundingRateDaily': 0.01125
        }
        """
        for data in self._get('funding', symbol, start, end, freq='2W'):
            yield list(map(self._funding_normalization, data))
