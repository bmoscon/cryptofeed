import time
from time import sleep
from datetime import datetime as dt
import json
import hashlib
import hmac
import calendar
import logging

from sortedcontainers import SortedDict as sd
import pandas as pd
import requests

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import BITFINEX, SELL, BUY, BID, ASK
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std


REQUEST_LIMIT = 5000
LOG = logging.getLogger('rest')


class Bitfinex(API):
    ID = BITFINEX
    api = "https://api-pub.bitfinex.com/v2/"

    def _nonce(self):
        return str(int(round(time.time() * 1000)))

    def _generate_signature(self, url: str, body=json.dumps({})):
        nonce = self._nonce()
        signature = "/api/" + url + nonce + body
        h = hmac.new(self.key_secret.encode('utf8'), signature.encode('utf8'), hashlib.sha384)
        signature = h.hexdigest()

        return {
            "bfx-nonce": nonce,
            "bfx-apikey": self.key_id,
            "bfx-signature": signature,
            "content-type": "application/json"
        }

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        if symbol[0] == 'f':
            # period is in days, from 2 to 30
            trade_id, timestamp, amount, price, period = trade
        else:
            trade_id, timestamp, amount, price = trade
            period = None
        timestamp = dt.utcfromtimestamp(timestamp / 1000.0).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        ret = {
            'timestamp': timestamp,
            'pair': pair_exchange_to_std(symbol),
            'id': trade_id,
            'feed': 'BITFINEX',
            'side': SELL if amount < 0 else BUY,
            'amount': abs(amount),
            'price': price,
        }

        if period:
            ret['period'] = period
        return ret

    def _dedupe(self, data, last):
        """
        Bitfinex does not support pagination, and using timestamps
        to paginate can lead to duplicate data being pulled
        """
        if len(last) == 0:
            return data

        ids = set([data[0] for data in last])
        ret = []

        for d in data:
            if d[0] in ids:
                continue
            ids.add(d[0])
            ret.append(d)

        return ret

    def _get_trades_hist(self, symbol, start_date, end_date, retry, retry_wait):
        last = []
        start = None
        end = None

        if start_date and end_date:
            start = pd.Timestamp(start_date)
            end = pd.Timestamp(end_date) - pd.Timedelta(nanoseconds=1)

            start = int(calendar.timegm(start.utctimetuple()) * 1000)
            end = int(calendar.timegm(end.utctimetuple()) * 1000)

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}trades/{symbol}/hist?limit={REQUEST_LIMIT}&start={start}&end={end}&sort=1")
            else:
                return requests.get(f"{self.api}trades/{symbol}/hist")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 - %s", self.ID, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self.handle_error(r, LOG)

            data = r.json()
            if data == []:
                LOG.warning("%s: No data for range %d - %d", self.ID, start, end)
            else:
                if data[-1][1] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.ID, start)
                    start += 1
                else:
                    start = data[-1][1]

            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = list(map(lambda x: self._trade_normalization(symbol, x), data))
            yield data

            if len(orig_data) < REQUEST_LIMIT:
                break

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = pair_std_to_exchange(symbol, self.ID)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

    def funding(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        symbol = f"f{symbol}"
        for data in self.trades(symbol, start=start, end=end, retry=retry, retry_wait=retry_wait):
            yield data

    def book(self, symbol, l3=False, retry=0, retry_wait=0):
        ret = {}
        sym = symbol
        funding = False

        if '-' not in symbol:
            ret[symbol] = {BID: sd(), ASK: sd()}
            symbol = f"f{symbol}"
            funding = True
        else:
            symbol = pair_std_to_exchange(symbol, self.ID)
            ret[symbol] = {BID: sd(), ASK: sd()}
            sym = symbol

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            precision = 'R0' if l3 is True else 'P0'
            return requests.get(f"{self.api}/book/{symbol}/{precision}?len=100")

        while True:
            r = helper()

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 - %s", self.ID, r.text)
                sleep(retry_wait)
                if retry == 0:
                    break
                continue
            elif r.status_code != 200:
                self.handle_error(r, LOG)

            data = r.json()
            break

        if l3:
            for entry in data:
                if funding:
                    order_id, period, price, amount = entry
                    update = (abs(amount), period)
                else:
                    order_id, price, amount = entry
                    update = abs(amount)
                side = BID if (amount > 0 and funding == False) or (amount < 0 and funding == True)  else ASK
                if price not in ret[sym][side]:
                    ret[sym][side][price] = {order_id: update}
                else:
                    ret[sym][side][price][order_id] = update
        else:
            for entry in data:
                if funding:
                    price, period, _, amount = entry
                    update = (abs(amount), period)
                else:
                    price, _, amount = entry
                    update = abs(amount)
                side = BID if (amount > 0 and funding == False) or (amount < 0 and funding == True)  else ASK
                ret[sym][side][price] = update
        return ret
