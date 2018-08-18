from time import sleep
import time
import hashlib
import hmac
from urllib.parse import urlparse

import requests
import pandas as pd

from cryptofeed.rest.api import API


API_MAX = 500
API_REFRESH = 300


class Bitmex(API):
    ID = 'bitmex'

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

    def _get_trades(self, symbol: str, start_date: str, end_date: str) -> list:
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
        total_data = []

        dates = pd.interval_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq="6H").tolist()
        if dates[-1].right < pd.Timestamp(end_date):
            dates.append(pd.Interval(dates[-1].right, pd.Timestamp(end_date)))

        for interval in dates:
            start = 0

            end = interval.right
            end -= pd.Timedelta(nanoseconds=1)

            start_date = str(interval.left).replace(" ", "T") + "Z"
            end_date = str(end).replace(" ", "T") + "Z"

            while True:
                endpoint = '/api/v1/trade?symbol={}&count={}&reverse=false&start={}&startTime={}&endTime={}'.format(symbol, API_MAX, start, start_date, end_date)
                header = None
                if self.key_id and self.key_secret:
                    header = self._generate_signature("GET", endpoint)
                r = requests.get('https://www.bitmex.com{}'.format(endpoint), headers=header)
                try:
                    limit = int(r.headers['X-RateLimit-Remaining'])
                    if r.status_code != 200:
                        r.raise_for_status()
                except:
                    print(r.json())
                    print(r.headers)
                    raise
                data = r.json()

                data = list(map(self._trade_normalization, data))

                total_data.extend(data)

                if len(data) != API_MAX:
                    break

                if limit < 1:
                    sleep(API_REFRESH)

                start += len(data)

        return total_data

    def _trade_normalization(self, trade: dict) -> dict:
        return {
            'timestamp': trade['timestamp'],
            'pair': trade['symbol'],
            'id': trade['trdMatchID'],
            'feed': 'BITMEX',
            'side': trade['side'],
            'amount': trade['size'],
            'price': trade['price']
        }

    def trades(self, symbol, start=None, end=None):
        if start and end:
            return self._get_trades(symbol, start, end)
