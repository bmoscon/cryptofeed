'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import decimal
import hashlib
import hmac
import time
from urllib.parse import urlparse

from yapic import json

from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook


class BitmexRestMixin(RestExchange):
    api = 'https://www.bitmex.com'
    rest_channels = (
        TRADES, TICKER, L2_BOOK
    )

    def _generate_signature(self, verb: str, url: str, data='') -> dict:
        """
        verb: GET/POST
        url: api endpoint
        data: body (if present)
        """
        expires = int(round(time.time()) + 30)

        parsedURL = urlparse(url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query

        if isinstance(data, (bytes, bytearray)):
            data = data.decode('utf8')

        message = verb + path + str(expires) + data

        signature = hmac.new(bytes(self.config.key_secret, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
        return {
            "api-expires": str(expires),
            "api-key": self.config.key_id,
            "api-signature": signature
        }

    def _trade_normalization(self, trade: dict) -> dict:
        return {
            'timestamp': self.timestamp_normalize(trade['timestamp']),
            'symbol': self.exchange_symbol_to_std_symbol(trade['symbol']),
            'id': trade['trdMatchID'],
            'feed': self.id,
            'side': BUY if trade['side'] == 'Buy' else SELL,
            'amount': decimal.Decimal(trade['size']),
            'price': decimal.Decimal(trade['price'])
        }

    async def _get(self, endpoint, symbol, retry_count, retry_delay):
        endpoint = f'/api/v1/{endpoint}?symbol={symbol}&reverse=true'
        header = {}

        if self.key_id and self.key_secret:
            header = self._generate_signature("GET", endpoint)
        header['Accept'] = 'application/json'
        data = await self.http_conn.read(f'{self.api}{endpoint}', header=header, retry_count=retry_count, retry_delay=retry_delay)
        return json.loads(data, parse_float=decimal.Decimal)

    async def ticker(self, symbol, start=None, end=None, retry_count=1, retry_delay=60):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        ret = await self._get('quote', symbol, retry_count, retry_delay)
        return self._ticker_normalization(ret[0])

    def _ticker_normalization(self, data: dict) -> dict:
        return {
            'bid': decimal.Decimal(data['bidPrice']),
            'ask': decimal.Decimal(data['askPrice']),
            'symbol': self.exchange_symbol_to_std_symbol(data['symbol']),
            'feed': self.id,
            'timestamp': data['timestamp'].timestamp()
        }

    async def trades(self, symbol, start=None, end=None, retry_count=1, retry_delay=60):
        """
        data format

        {
            'timestamp': '2018-01-01T23:59:59.907Z',
            'symbol': 'XBTUSD',
            'side': 'Buy',
            'size': 1900,
            'price': 13477,
            'tickDirection': 'ZeroPlusTick',
            'trdMatchID': '14fcc8d7-d056-768d-3c46-1fdf98728343',
            'grossValue': 14098000,
            'homeNotional': 0.14098,
            'foreignNotional': 1900
        }
        """
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)

        data = await self._get('trade', symbol, retry_count, retry_delay)
        yield list(map(self._trade_normalization, data))

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        ret = OrderBook(self.id, symbol)

        data = await self._get('orderBook/L2', self.std_symbol_to_exchange_symbol(symbol), retry_count, retry_delay)
        for update in data:
            side = ASK if update['side'] == 'Sell' else BID
            ret.book[side][decimal.Decimal(update['price'])] = decimal.Decimal(update['size'])
        return ret
