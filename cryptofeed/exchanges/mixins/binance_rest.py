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
from urllib.parse import urlencode

from yapic import json

from cryptofeed.defines import BALANCES, BUY, CANCEL_ORDER, CANDLES, DELETE, FILL_OR_KILL, GET, GOOD_TIL_CANCELED, IMMEDIATE_OR_CANCEL, LIMIT, MARKET, ORDERS, ORDER_STATUS, PLACE_ORDER, POSITIONS, POST, SELL, TRADES
from cryptofeed.exchange import RestExchange
from cryptofeed.types import Candle


LOG = logging.getLogger('cryptofeed.rest')


class BinanceRestMixin(RestExchange):
    api = "https://api.binance.com/api/v3/"
    rest_channels = (
        TRADES, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, ORDERS, CANDLES
    )
    order_options = {
        LIMIT: 'LIMIT',
        MARKET: 'MARKET',
        FILL_OR_KILL: 'FOK',
        IMMEDIATE_OR_CANCEL: 'IOC',
        GOOD_TIL_CANCELED: 'GTC',
    }

    def _nonce(self):
        return str(int(round(time.time() * 1000)))

    def _generate_signature(self, query_string: str):
        h = hmac.new(self.key_secret.encode('utf8'), query_string.encode('utf8'), hashlib.sha256)
        return h.hexdigest()

    async def _request(self, method: str, endpoint: str, auth: bool = False, payload={}, api=None):
        query_string = urlencode(payload)
        if auth:
            if query_string:
                query_string = '{}&timestamp={}'.format(query_string, self._nonce())
            else:
                query_string = 'timestamp={}'.format(self._nonce())

        if not api:
            api = self.api

        url = f'{api}{endpoint}?{query_string}'
        header = {}
        if auth:
            signature = self._generate_signature(query_string)
            url += f'&signature={signature}'
            header = {
                "X-MBX-APIKEY": self.key_id,
            }
        if method == GET:
            data = await self.http_conn.read(url, header=header)
        elif method == POST:
            data = await self.http_conn.write(url, msg=None, header=header)
        elif method == DELETE:
            data = await self.http_conn.delete(url, header=header)
        return json.loads(data, parse_float=Decimal)

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

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        ep = f'{self.api}klines?symbol={sym}&interval={interval}&limit=1000'

        start, end = self._interval_normalize(start, end)
        if start and end:
            start = int(start * 1000)
            end = int(end * 1000)

        while True:
            if start and end:
                endpoint = f'{ep}&startTime={start}&endTime={end}'
            else:
                endpoint = ep
            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)
            start = data[-1][6]
            data = [Candle(self.id, symbol, self.timestamp_normalize(e[0]), self.timestamp_normalize(e[6]), interval, e[8], Decimal(e[1]), Decimal(e[4]), Decimal(e[2]), Decimal(e[3]), Decimal(e[5]), True, self.timestamp_normalize(e[6]), raw=e) for e in data]
            yield data

            if len(data) < 1000 or end is None:
                break
            await asyncio.sleep(1 / self.request_limit)

    # Trading APIs
    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, time_in_force=None, test=False):
        if order_type == MARKET and price:
            raise ValueError('Cannot specify price on a market order')
        if order_type == LIMIT:
            if not price:
                raise ValueError('Must specify price on a limit order')
            if not time_in_force:
                raise ValueError('Must specify time in force on a limit order')
        ot = self.normalize_order_options(order_type)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        parameters = {
            'symbol': sym,
            'side': 'BUY' if side is BUY else 'SELL',
            'type': ot,
            'quantity': str(amount),
        }
        if price:
            parameters['price'] = str(price)
        if time_in_force:
            parameters['timeInForce'] = self.normalize_order_options(time_in_force)

        data = await self._request(POST, 'test' if test else 'order', auth=True, payload=parameters)
        return data

    async def cancel_order(self, order_id: str, symbol: str):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._request(DELETE, 'order', auth=True, payload={'symbol': sym, 'orderId': order_id})
        return data

    async def balances(self):
        data = await self._request(GET, 'account', auth=True)
        return data['balances']

    async def orders(self, symbol: str = None):
        data = await self._request(GET, 'openOrders', auth=True, payload={'symbol': self.std_symbol_to_exchange_symbol(symbol)} if symbol else {})
        return data

    async def order_status(self, order_id: str):
        data = await self._request(GET, 'order', auth=True, payload={'orderId': order_id})
        return data


class BinanceFuturesRestMixin(BinanceRestMixin):
    api = 'https://fapi.binance.com/fapi/v1/'
    rest_channels = (
        TRADES, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, ORDERS, POSITIONS
    )

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, time_in_force=None):
        data = await super().place_order(symbol, side, order_type, amount, price=price, time_in_force=time_in_force, test=False)
        return data

    async def balances(self):
        data = await self._request(GET, 'account', auth=True, api='https://fapi.binance.com/fapi/v2/')
        return data['assets']

    async def positions(self):
        data = await self._request(GET, 'account', auth=True, api='https://fapi.binance.com/fapi/v2/')
        return data['positions']


class BinanceDeliveryRestMixin(BinanceRestMixin):
    api = 'https://dapi.binance.com/dapi/v1/'
    rest_channels = (
        TRADES, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, ORDERS, POSITIONS
    )

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, time_in_force=None):
        data = await super().place_order(symbol, side, order_type, amount, price=price, time_in_force=time_in_force, test=False)
        return data

    async def balances(self):
        data = await self._request(GET, 'account', auth=True)
        return data['assets']

    async def positions(self):
        data = await self._request(GET, 'account', auth=True)
        return data['positions']


class BinanceUSRestMixin(BinanceRestMixin):
    api = 'https://api.binance.us/api/v3/'
    rest_channels = (
        TRADES
    )
