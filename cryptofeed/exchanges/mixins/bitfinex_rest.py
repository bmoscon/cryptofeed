'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import time
from decimal import Decimal
from time import sleep

import pandas as pd
import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BITFINEX, BUY, SELL
from cryptofeed.exchanges import Bitfinex as BitfinexEx
from cryptofeed.rest import RestAPI, request_retry


REQUEST_LIMIT = 5000
RATE_LIMIT_SLEEP = 3


class Bitfinex(RestAPI):
    id = BITFINEX
    api = "https://api-pub.bitfinex.com/v2/"
    info = BitfinexEx()

    def _get(self, endpoint, retry, retry_wait):
        @request_retry(self.id, retry, retry_wait)
        def helper():
            r = requests.get(f"{self.api}{endpoint}")
            self._handle_error(r)
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
            "bfx-nonce": nonce,
            "bfx-apikey": self.config.key_id,
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

        ret = {
            'timestamp': self.timestamp_normalize(timestamp),
            'symbol': self.info.exchange_symbol_to_std_symbol(symbol),
            'id': trade_id,
            'feed': self.id,
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

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = self._timestamp(start_date)
            end = self._timestamp(end_date) - pd.Timedelta(nanoseconds=1)

            start = int(start.timestamp() * 1000)
            end = int(end.timestamp() * 1000)

        @request_retry(self.id, retry, retry_wait)
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
                self.log.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()
            if data == []:
                self.log.warning("%s: No data for range %d - %d", self.id, start, end)
            else:
                if data[-1][1] == start:
                    self.log.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.id, start)
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
        symbol = self.info.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades_hist(symbol, start, end, retry, retry_wait):
            yield data

    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"ticker/{sym}", retry, retry_wait)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data[0]),
                'ask': Decimal(data[2])
                }

    def funding(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = f"f{symbol}"
        for data in self.trades(symbol, start=start, end=end, retry=retry, retry_wait=retry_wait):
            yield data

    def l2_book(self, symbol: str, retry=0, retry_wait=0):
        return self._book(symbol, retry=retry, retry_wait=retry_wait)

    def l3_book(self, symbol: str, retry=0, retry_wait=0):
        return self._book(symbol, l3=True, retry=retry, retry_wait=retry_wait)

    def _book(self, symbol: str, l3=False, retry=0, retry_wait=0):
        ret = {}
        sym = symbol
        funding = False

        if '-' not in symbol:
            ret[symbol] = {BID: sd(), ASK: sd()}
            symbol = f"f{symbol}"
            funding = True
        else:
            symbol = self.info.std_symbol_to_exchange_symbol(symbol)
            ret[symbol] = {BID: sd(), ASK: sd()}
            sym = symbol

        @request_retry(self.id, retry, retry_wait)
        def helper():
            precision = 'R0' if l3 is True else 'P0'
            return requests.get(f"{self.api}/book/{symbol}/{precision}?len=100")

        while True:
            r = helper()

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                self.log.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                if retry == 0:
                    break
                continue
            elif r.status_code != 200:
                self._handle_error(r)

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
                side = BID if (amount > 0 and not funding) or (amount < 0 and funding) else ASK
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
                side = BID if (amount > 0 and not funding) or (amount < 0 and funding) else ASK
                ret[sym][side][price] = update
        return ret