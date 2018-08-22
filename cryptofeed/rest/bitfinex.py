import time
from time import sleep
from datetime import datetime as dt

import pandas as pd
import requests

from cryptofeed.rest.api import API
from cryptofeed.feeds import BITFINEX
from cryptofeed.standards import pair_std_to_exchange


REQUEST_LIMIT = 1000


class Bitfinex(API):
    ID = BITFINEX

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

    def _dedupe(self, data, last):
        """
        Bitfinex does not support pagination, and using timestamps
        to paginate can lead to duplicate data being pulled
        """
        if len(last) == 0:
            return data

        ids = set([id for id, _, _, _ in last])
        ret = []

        for d in data:
            if d[0] in ids:
                continue
            ids.add(d[0])
            ret.append(d)

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date):
        last = []

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

            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(orig_data) < REQUEST_LIMIT:
                break

    def trades(self, symbol: str, start=None, end=None):
        symbol = pair_std_to_exchange(symbol, self.ID)
        if start and end:
            for data in self._get_trades_hist(symbol, start, end):
                yield data
