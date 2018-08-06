import time
from time import sleep
from datetime import datetime as dt

import pandas as pd
import requests

from cryptofeed.rest.api import API


REQUEST_LIMIT = 1000


class Bitfinex(API):
    ID = 'bitfinex'

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        trade_id, timestamp, amount, price = trade
        timestamp = dt.fromtimestamp(int(timestamp / 1000)).strftime('%Y-%m-%d %H:%M:%S')

        return {
            'timestamp': timestamp,
            'pair': symbol,
            'id': trade_id,
            'feed': 'BITFINEX',
            'side': 'Sell' if amount < 0 else 'Buy',
            'amount': abs(amount),
            'price': price
        }

    def _dedupe(self, data):
        ids = set()
        ret = []

        for d in data:
            if d['id'] in ids:
                continue
            ids.add(d['id'])
            ret.append(d)

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date):
        total_data = []

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date) - pd.Timedelta(nanoseconds=1)

        start = int(time.mktime(start.timetuple()) * 1000)
        end = int(time.mktime(end.timetuple()) * 1000)

        while True:
            r = requests.get("https://api.bitfinex.com/v2/trades/{}/hist?limit={}&start={}&end={}&sort=1".format(symbol, REQUEST_LIMIT, start, end))
            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code != 200:
                print(r.headers)
                print(r.json())
                r.raise_for_status()

            data = r.json()
            start = data[-1][1]

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            total_data.extend(data)

            if len(data) < REQUEST_LIMIT:
                break

        total_data = list(self._dedupe(total_data))
        return total_data

    def trades(self, symbol: str, start=None, end=None):
        if start and end:
            return self._get_trades_hist(symbol, start, end)
