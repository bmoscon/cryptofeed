'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from time import sleep
from datetime import datetime as dt
import logging

import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, SELL, TRADES
from cryptofeed.connection import request_retry
from cryptofeed.exchange import RestExchange


LOG = logging.getLogger('feedhandler')


class DeribitRestMixin(RestExchange):
    api = "https://www.deribit.com/api/v2/public/"
    sandbox_api = 'https://test.deribit.com/api/v2/public/'
    rest_channels = (TRADES, L2_BOOK)

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        for data in self._get_trades(symbol, start, end, retry, retry_wait):
            yield data

    def _get_trades(self, instrument, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = dt.now()
            start = self._datetime_normalize(start_date)
            end = self._datetime_normalize(end_date)

            start = int(start * 1000)
            end = int(end * 1000)

        @request_retry(self.id, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}get_last_trades_by_instrument_and_time?&start_timestamp={start}&end_timestamp={end}&instrument_name={instrument}&include_old=true&count=1000")
            else:
                return requests.get(f"{self.api}get_last_trades_by_instrument?instrument_name={instrument}&include_old=true&count=1000")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r)
            else:
                sleep(1 / self.request_limit)

            data = json.loads(r.text, parse_float=Decimal)["result"]["trades"]
            if data == []:
                LOG.warning("%s: No data for range %d - %d",
                            self.id, start, end)
            else:
                if data[-1]["timestamp"] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.id, start)
                    start += 1
                else:
                    start = data[-1]["timestamp"]

            orig_data = data
            data = [self._trade_normalization(x) for x in data]
            yield data

            if len(orig_data) < 1000 or not start or not end:
                break

    def _trade_normalization(self, trade: list) -> dict:

        ret = {
            'timestamp': self.timestamp_normalize(trade["timestamp"]),
            'symbol': self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
            'id': int(trade["trade_id"]),
            'feed': self.id,
            'side': BUY if trade["direction"] == 'buy' else SELL,
            'amount': Decimal(trade["amount"]),
            'price': Decimal(trade["price"]),
        }
        return ret

    def l2_book(self, symbol: str, retry=0, retry_wait=0):
        return self._book(symbol, retry=retry, retry_wait=retry_wait)

    def _book(self, symbol: str, retry=0, retry_wait=0):
        ret = {}
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        ret = {BID: sd(), ASK: sd()}

        @request_retry(self.id, retry, retry_wait)
        def helper():
            return requests.get(f"{self.api}get_order_book?depth=10000&instrument_name={symbol}")

        while True:
            r = helper()

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.id, r.url, r.text)
                sleep(retry_wait)
                if retry == 0:
                    break
                continue
            elif r.status_code != 200:
                self._handle_error(r)

            data = json.loads(r.text, parse_float=Decimal)
            break

        for side, key in ((BID, 'bids'), (ASK, 'asks')):
            for entry_bid in data["result"][key]:
                price, amount = entry_bid
                ret[side][price] = amount

        return ret
