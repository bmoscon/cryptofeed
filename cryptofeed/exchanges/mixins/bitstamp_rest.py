'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import CANDLES
from cryptofeed.exchange import RestExchange
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Candle


LOG = logging.getLogger('cryptofeed.rest')


class BitstampRestMixin(RestExchange):
    api = "https://www.bitstamp.net/api/v2/"
    rest_channels = (CANDLES)
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '3d'}

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        interval_sec = timedelta_str_to_sec(interval)
        base = f'{self.api}ohlc/{sym}/?step={interval_sec}&limit=1000'
        start, end = self._interval_normalize(start, end)

        while True:
            endpoint = base
            if start and end:
                endpoint = f'{base}&start={int(start)}&end={int(end)}'

            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)['data']['ohlc']
            data = [Candle(self.id, symbol, float(e['timestamp']), float(e['timestamp']) + interval_sec, interval, None, Decimal(e['open']), Decimal(e['close']), Decimal(e['high']), Decimal(e['low']), Decimal(e['volume']), True, float(e['timestamp']), raw=e) for e in data]
            yield data

            end = data[0].start - interval_sec
            if not start or start >= end:
                break
            await asyncio.sleep(1 / self.request_limit)
