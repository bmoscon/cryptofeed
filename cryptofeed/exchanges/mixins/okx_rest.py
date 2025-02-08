'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.exchange import RestExchange
from cryptofeed.types import Candle
from cryptofeed.defines import CANDLES
from cryptofeed.util.time import timedelta_str_to_sec

LOG = logging.getLogger('feedhandler')


class OKXRestMixin(RestExchange):
    api = "https://www.okx.com/api/v5/"
    rest_channels = (
        CANDLES,
    )
    order_options = {

    }

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        base_endpoint = f"{self.api}market/history-candles?instId={sym}"
        start, end = self._interval_normalize(start, end)
        end += 1  # timestamps querying is not inclusive on OKX
        start -= 1
        offset = timedelta_str_to_sec(interval)

        if not interval.endswith('m'):
            interval[-1] = interval[-1].upper()

        while True:
            if start and end:
                endpoint = f"{base_endpoint}&before={int(start * 1000)}&after={int(end * 1000)}&bar={interval}&limit=300"
            r = await self.http_conn.read(endpoint, retry_delay=retry_delay, retry_count=retry_count)
            data = json.loads(r, parse_float=Decimal)
            data = [Candle(self.id, symbol, int(e[0]) / 1000, int(e[0]) / 1000 + offset, interval, None, Decimal(e[1]), Decimal(e[4]), Decimal(e[2]), Decimal(e[3]), Decimal(e[5]), True, int(e[0]) / 1000, raw=e) for e in reversed(data['data'])]
            yield data

            if len(data) < 300 or start >= end:
                break
            end = data[0].timestamp

            await asyncio.sleep(1 / self.request_limit)
