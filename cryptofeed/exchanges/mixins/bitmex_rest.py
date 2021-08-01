'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import decimal
import hashlib
import hmac
import time
from time import sleep
from urllib.parse import urlparse

from yapic import json
import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exchange import RestExchange
from cryptofeed.connection import request_retry


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

    def _get(self, ep, symbol, retry, retry_wait):
        @request_retry(self.id, retry, retry_wait)
        def helper():
            endpoint = f'/api/v1/{ep}?symbol={symbol}&reverse=true'
            header = {}
            if self.key_id and self.key_secret:
                header = self._generate_signature("GET", endpoint)
            header['Accept'] = 'application/json'
            return requests.get('{}{}'.format(self.api, endpoint), headers=header)

        while True:
            r = helper()

            if r.status_code in {502, 504}:
                self.log.warning("%s: %d for URL %s - %s", self.id, r.status_code, r.url, r.text)
                sleep(retry_wait)
                continue
            elif r.status_code == 429:
                sleep(300)
                continue
            elif r.status_code != 200:
                self._handle_error(r)

            yield json.loads(r.text, parse_float=decimal.Decimal)
            break

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

    def ticker(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        ret = list(self._get('quote', symbol, retry, retry_wait))[0][0]
        return self._ticker_normalization(ret)

    def _ticker_normalization(self, data: dict) -> dict:
        return {
            'bid': decimal.Decimal(data['bidPrice']),
            'ask': decimal.Decimal(data['askPrice']),
            'symbol': self.exchange_symbol_to_std_symbol(data['symbol']),
            'feed': self.id,
            'timestamp': data['timestamp'].timestamp()
        }

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
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
        for data in self._get('trade', symbol, retry, retry_wait):
            yield list(map(self._trade_normalization, data))

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        ret = {BID: sd(), ASK: sd()}
        data = next(self._get('orderBook/L2', self.std_symbol_to_exchange_symbol(symbol), retry, retry_wait))
        for update in data:
            side = ASK if update['side'] == 'Sell' else BID
            ret[side][update['price']] = update['size']
        return ret
