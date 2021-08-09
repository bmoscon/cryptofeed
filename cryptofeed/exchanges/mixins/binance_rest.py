'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import hashlib
import hmac
import logging
import time

from yapic import json

from cryptofeed.defines import BUY, SELL, TRADES
from cryptofeed.exchange import RestExchange


LOG = logging.getLogger('cryptofeed.rest')


class BinanceRestMixin(RestExchange):
    api = "https://api.binance.com/api/v3/"
    rest_channels = (
        TRADES
    )

    def _nonce(self):
        return str(int(round(time.time() * 1000)))

    def _generate_signature(self, url: str, body=json.dumps({})):
        nonce = self._nonce()
        signature = "/api/" + url + nonce + body
        h = hmac.new(self.config.key_secret.encode('utf8'), signature.encode('utf8'), hashlib.sha384)
        signature = h.hexdigest()

        return {
            "X-MBX-APIKEY": self.config.key_id,
            "signature": signature,
            "content-type": "application/json"
        }

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)
        if start and end:
            start = int(start * 1000)
            end = int(end * 1000)

        while True:
            if start and end:
                endpoint = f"{self.api}aggTrades?symbol={symbol}&limit=1000&startTime={start}&endTime={end}"
            else:
                endpoint = f"{self.api}aggTrades?symbol={symbol}&limit=1000"

            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)

            if data:
                if data[-1]['T'] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.id, start)
                    start += 1
                else:
                    start = data[-1]['T']

            yield [self._trade_normalization(symbol, d) for d in data]

            if len(data) < 1000 or end is None:
                break
            await asyncio.sleep(1 / self.request_limit)

    def _trade_normalization(self, symbol: str, trade: list) -> dict:
        ret = {
            'timestamp': self.timestamp_normalize(trade['T']),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['a'],
            'feed': self.id,
            'side': BUY if trade['m'] else SELL,
            'amount': abs(Decimal(trade['q'])),
            'price': Decimal(trade['p']),
        }
        return ret


class BinanceFuturesRestMixin(BinanceRestMixin):
    api = "https://fapi.binance.com/fapi/v1/"
    rest_channels = (
        TRADES
    )


class BinanceDeliveryRestMixin(BinanceRestMixin):
    api = "https://dapi.binance.com/dapi/v1/"
    rest_channels = (
        TRADES
    )
