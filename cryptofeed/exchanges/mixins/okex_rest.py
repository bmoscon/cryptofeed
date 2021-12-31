'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
@Author: bastien.enjalbert@gmail.com
'''
from datetime import datetime as dt
from decimal import Decimal
import logging
import time

from yapic import json

from cryptofeed.exchange import RestExchange
from cryptofeed.types import Candle
from cryptofeed.util.time import timedelta_str_to_sec

LOG = logging.getLogger('feedhandler')


# API docs https://www.okex.com/docs/en/
# 20 calls per 2 seconds for historical data (https://www.okex.com/docs/en/#spot-line_history)
#
class OKExRestMixin(RestExchange):
    api = "https://okex.com/api/"
    rest_channels = (

    )
    order_options = {

    }
    candle_mappings = {'1m': '60', '3m': '180', '5m': '300', '15m': '900', '30m': '1800', '1h': '3600', '2h': '7200', '4h': '14400',
                       '6h': '21600', '12h': '43200', '1d': '86400', '7d': '604800'}

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        _interval = self.candle_mappings[interval]
        sym = self.std_symbol_to_exchange_symbol(symbol)
        base_endpoint = f"{self.api}spot/v3/instruments/{sym}"
        start, end = self._interval_normalize(start, end)
        offset = timedelta_str_to_sec(interval)

        while True:
            if start and end:
                # maximum candle limit is 300
                endpoint = f"{base_endpoint}/history/candles?start={self._to_isoformat(end)}&end={self._to_isoformat(start)}"\
                           f"&granularity={offset}&limit=300"
            r = await self.http_conn.read(endpoint, retry_delay=retry_delay, retry_count=retry_count)
            data = json.loads(r, parse_float=Decimal)
            if not isinstance(data[0], list):
                data = [data]
            data = [Candle(self.id, symbol, self._datetime_normalize(e[0]), self._datetime_normalize(e[0]) + offset,
                           interval, None, Decimal(e[1]), Decimal(e[2]), Decimal(e[3]), Decimal(e[4]), Decimal(e[5]),
                           True, self._datetime_normalize(e[0]), raw=e) for e in data]

            yield data
            if not end or len(data) < 10000:
                break
            start = data[-1].start + offset

            time.sleep(2) # Hardcoded : TODO : optimize and use the 20 requests per 2 seconds slots

    def _to_isoformat(self, timestamp):
        """Required for okex (ISO 8601)
        """
        return dt.utcfromtimestamp(timestamp).isoformat(sep='T', timespec='milliseconds') + 'Z'