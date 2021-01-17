import logging
from time import sleep

import pandas as pd
import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, DERIBIT, SELL
from cryptofeed.rest.api import API, request_retry
from cryptofeed.standards import symbol_std_to_exchange, timestamp_normalize


REQUEST_LIMIT = 1000
RATE_LIMIT_SLEEP = 0.2
LOG = logging.getLogger('rest')


class Deribit(API):
    ID = DERIBIT
    api = "https://www.deribit.com/api/v2/public/"

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        symbol = symbol_std_to_exchange(symbol, self.ID)
        for data in self._get_trades(symbol, start, end, retry, retry_wait):
            yield data

    def _get_trades(self, instrument, start_date, end_date, retry, retry_wait):
        start = None
        end = None

        if start_date:
            if not end_date:
                end_date = pd.Timestamp.utcnow()
            start = API._timestamp(start_date)
            end = API._timestamp(end_date) - pd.Timedelta(nanoseconds=1)

            start = int(start.timestamp() * 1000)
            end = int(end.timestamp() * 1000)

        @request_retry(self.ID, retry, retry_wait)
        def helper(start, end):
            if start and end:
                return requests.get(f"{self.api}get_last_trades_by_instrument_and_time?&start_timestamp={start}&end_timestamp={end}&instrument_name={instrument}&include_old=true&count={REQUEST_LIMIT}")
            else:
                return requests.get(f"{self.api}get_last_trades_by_instrument?instrument_name={instrument}&include_old=true&count={REQUEST_LIMIT}")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                sleep(RATE_LIMIT_SLEEP)

            data = r.json()["result"]["trades"]
            if data == []:
                LOG.warning("%s: No data for range %d - %d",
                            self.ID, start, end)
            else:
                if data[-1]["timestamp"] == start:
                    LOG.warning(
                        "%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.ID, start)
                    start += 1
                else:
                    start = data[-1]["timestamp"]

            orig_data = data
            data = [self._trade_normalization(x) for x in data]
            yield data

            if len(orig_data) < REQUEST_LIMIT or not start or not end:
                break

    def _trade_normalization(self, trade: list) -> dict:

        ret = {
            'timestamp': timestamp_normalize(self.ID, trade["timestamp"]),
            'symbol': trade["instrument_name"],
            'id': int(trade["trade_id"]),
            'feed': self.ID,
            'side': BUY if trade["direction"] == 'buy' else SELL,
            'amount': trade["amount"],
            'price': trade["price"],
        }
        return ret

    def l2_book(self, symbol: str, retry=0, retry_wait=0):
        return self._book(symbol, retry=retry, retry_wait=retry_wait)

    def _book(self, symbol: str, retry=0, retry_wait=0):
        ret = {}
        symbol = symbol_std_to_exchange(symbol, self.ID)
        ret[symbol] = {BID: sd(), ASK: sd()}

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            return requests.get(f"{self.api}get_order_book?depth=10000&instrument_name={symbol}")

        while True:
            r = helper()

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
                continue
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
                if retry == 0:
                    break
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)

            data = r.json()
            break

        for side, key in ((BID, 'bids'), (ASK, 'asks')):
            for entry_bid in data["result"][key]:
                price, amount = entry_bid
                ret[symbol][side][price] = amount

        return ret
