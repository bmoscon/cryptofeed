import time
from time import sleep
import yaml

import pandas as pd
import requests


REQUEST_LIMIT = 1000


class Bitfinex:
    def __init__(self, config):
        self.key_id, self.key_secret = None, None
        if not config:
            config = "config.yaml"
        
        try:
            with open(config, 'r') as fp:
                data = yaml.load(fp)
                self.key_id = data['bitfinex']['key_id']
                self.key_secret = data['bitfinex']['key_secret']
        except:
            pass

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
            total_data.extend(data)

            if len(data) < REQUEST_LIMIT:
                break

            start = data[-1][1]

        return total_data

    def trades(self, symbol: str, start=None, end=None):
        if start and end:
            return self._get_trades_hist(symbol, start, end)
