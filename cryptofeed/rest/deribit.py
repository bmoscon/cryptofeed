from time import sleep
import logging
import pandas as pd
import requests

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import DERIBIT, SELL, BUY
from cryptofeed.standards import pair_std_to_exchange, timestamp_normalize


REQUEST_LIMIT = 1000
LOG = logging.getLogger('rest')


class Deribit(API):
    ID = DERIBIT
    api = "https://www.deribit.com/api/v2/public/"

    def trades(self, instrument: str, start=None, end=None, retry=None, retry_wait=10):
        instrument = pair_std_to_exchange(instrument, self.ID)
        for data in self._get_trades(instrument, start, end, retry, retry_wait):
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
                return requests.get(f"{self.api}get_last_trades_by_instrument_and_time/")

        while True:
            r = helper(start, end)

            if r.status_code == 429:
                sleep(int(r.headers['Retry-After']))
            elif r.status_code == 500:
                LOG.warning("%s: 500 for URL %s - %s", self.ID, r.url, r.text)
                sleep(retry_wait)
            elif r.status_code != 200:
                self._handle_error(r, LOG)

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
            data = list(map(lambda x: self._trade_normalization(x), data))
            yield data

            if len(orig_data) < REQUEST_LIMIT:
                break

    def _trade_normalization(self, trade: list) -> dict:

        ret = {
            'timestamp': timestamp_normalize(self.ID, trade["timestamp"]),
            'pair': trade["instrument_name"],
            'id': int(trade["trade_id"]),
            'feed': self.ID,
            'side': BUY if trade["direction"] == 'buy' else SELL,
            'amount': trade["amount"],
            'price':  trade["price"],
        }
        return ret
