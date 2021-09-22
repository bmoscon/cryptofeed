'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from datetime import datetime, timezone

from yapic import json

from cryptofeed.defines import CANDLES
from cryptofeed.exchange import RestExchange
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Candle


LOG = logging.getLogger('cryptofeed.rest')


class UpbitRestMixin(RestExchange):
    api = "https://api.upbit.com/v1/"
    rest_channels = (CANDLES)
    valid_candle_intervals = {'1m', '3m', '5m', '10m', '15m', '30m', '1h', '4h', '1d', '1w', '1M'}

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        '''
        [
            {
            "market": "KRW-BTC",
            "candle_date_time_utc": "2021-09-11T00:32:00",
            "candle_date_time_kst": "2021-09-11T09:32:00",
            "opening_price": 55130000,
            "high_price": 55146000,
            "low_price": 55104000,
            "trade_price": 55145000,
            "timestamp": 1631320340367,
            "candle_acc_trade_price": 136592120.21198,
            "candle_acc_trade_volume": 2.47785284,
            "unit": 1
            },
            ...
        ]
        '''
        sym = self.std_symbol_to_exchange_symbol(symbol)
        offset = timedelta_str_to_sec(interval)
        interval_mins = int(timedelta_str_to_sec(interval) / 60)
        if interval == '1d':
            base = f'{self.api}candles/days/?market={sym}&count=200'
        elif interval == '1w':
            base = f'{self.api}candles/weeks/?market={sym}&count=200'
        elif interval == '1M':
            base = f'{self.api}candles/months/?market={sym}&count=200'
        else:
            base = f'{self.api}candles/minutes/{interval_mins}?market={sym}&count=200'
        start, end = self._interval_normalize(start, end)

        def _ts_norm(timestamp: datetime) -> float:
            # Upbit sends timezone naïve datetimes, so need to force to UTC before converting to timestamp
            assert timestamp.tzinfo is None
            return timestamp.replace(tzinfo=timezone.utc).timestamp()

        def retain(c: Candle, _last: set):
            if start and end:
                return c.start <= end and c.start not in _last
            return True

        _last = set()
        while True:
            endpoint = base
            if start and end:
                end_timestamp = datetime.utcfromtimestamp(start + offset * 200)
                end_timestamp = end_timestamp.replace(microsecond=0).isoformat() + 'Z'
                endpoint = f'{base}&to={end_timestamp}'

            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)
            data = [Candle(self.id, symbol, _ts_norm(e['candle_date_time_utc']), _ts_norm(e['candle_date_time_utc']) + interval_mins * 60, interval, None, Decimal(e['opening_price']), None, Decimal(e['high_price']), Decimal(e['low_price']), Decimal(e['candle_acc_trade_volume']), True, float(e['timestamp']) / 1000, raw=e) for e in data]
            data = list(sorted([c for c in data if retain(c, _last)], key=lambda x: x.start))
            yield data

            # exchange downtime can cause gaps in candles, and because of the way pagination works, there will be overlap in ranges that
            # cover the downtime. Solution: remove duplicates by storing last values returned to client.
            _last = set([c.start for c in data])

            start = data[-1].start + offset
            if not end or start >= end:
                break
            await asyncio.sleep(1 / self.request_limit)
