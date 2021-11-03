'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import base64
from cryptofeed.util.time import timedelta_str_to_sec
import hmac
import hashlib
from datetime import datetime as dt
from decimal import Decimal
import logging
import time
from typing import Optional, Union

from yapic import json

from cryptofeed.defines import BUY, CANCELLED, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, MAKER_OR_CANCEL, MARKET, OPEN, PARTIAL, PENDING, SELL, TRADES, TICKER, L2_BOOK, L3_BOOK, ORDER_INFO, ORDER_STATUS, CANDLES, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY, LIMIT
from cryptofeed.exceptions import UnexpectedMessage
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook, Candle


LOG = logging.getLogger('feedhandler')


class CoinbaseRestMixin(RestExchange):
    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, L3_BOOK, ORDER_INFO, ORDER_STATUS, CANDLES, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    order_options = {
        LIMIT: 'limit',
        MARKET: 'market',
        FILL_OR_KILL: {'time_in_force': 'FOK'},
        IMMEDIATE_OR_CANCEL: {'time_in_force': 'IOC'},
        MAKER_OR_CANCEL: {'post_only': 1},
    }

    def _order_status(self, data: dict):
        if 'status' not in data:
            raise UnexpectedMessage(f"Message from exchange: {data}")
        status = data['status']
        if data['status'] == 'done' and data['done_reason'] == 'canceled':
            status = PARTIAL
        elif data['status'] == 'done':
            status = FILLED
        elif data['status'] == 'open':
            status = OPEN
        elif data['status'] == 'pending':
            status = PENDING
        elif data['status'] == CANCELLED:
            status = CANCELLED

        if 'price' not in data:
            price = Decimal(data['executed_value']) / Decimal(data['filled_size'])
        else:
            price = Decimal(data['price'])

        return {
            'order_id': data['id'],
            'symbol': data['product_id'],
            'side': BUY if data['side'] == 'buy' else SELL,
            'order_type': LIMIT if data['type'] == 'limit' else MARKET,
            'price': price,
            'total': Decimal(data['size']),
            'executed': Decimal(data['filled_size']),
            'pending': Decimal(data['size']) - Decimal(data['filled_size']),
            'timestamp': data['done_at'].timestamp() if 'done_at' in data else data['created_at'].timestamp(),
            'order_status': status
        }

    def _generate_signature(self, endpoint: str, method: str, body=''):
        timestamp = str(time.time())
        message = ''.join([timestamp, method, endpoint, body])
        hmac_key = base64.b64decode(self.config.key_secret)
        signature = hmac.new(hmac_key, message.encode('ascii'), hashlib.sha256)
        signature_b64 = base64.b64encode(signature.digest()).decode('utf-8')

        return {
            'CB-ACCESS-KEY': self.config.key_id,  # The api key as a string.
            'CB-ACCESS-SIGN': signature_b64,  # The base64-encoded signature (see Signing a Message).
            'CB-ACCESS-TIMESTAMP': timestamp,  # A timestamp for your request.
            'CB-ACCESS-PASSPHRASE': self.key_passphrase,  # The passphrase you specified when creating the API key
            'Content-Type': 'Application/JSON',
        }

    async def _request(self, method: str, endpoint: str, auth: bool = False, body=None, retry_count=1, retry_delay=60):
        api = self.sandbox_api if self.sandbox else self.api
        header = None
        if auth:
            header = self._generate_signature(endpoint, method, body=json.dumps(body) if body else '')

        if method == "GET":
            data = await self.http_conn.read(f'{api}{endpoint}', header=header)
        elif method == 'POST':
            data = await self.http_conn.write(f'{api}{endpoint}', msg=body, header=header)
        elif method == 'DELETE':
            data = await self.http_conn.delete(f'{api}{endpoint}', header=header)
        return json.loads(data, parse_float=Decimal)

    async def _date_to_trade(self, symbol: str, timestamp: float) -> int:
        """
        Coinbase uses trade ids to query historical trades, so
        need to search for the start date
        """
        upper = await self._request('GET', f'/products/{symbol}/trades')
        upper = upper[0]['trade_id']
        lower = 0
        bound = (upper - lower) // 2
        while True:
            data = await self._request('GET', f'/products/{symbol}/trades?after={bound}')
            data = list(reversed(data))
            if len(data) == 0:
                return bound
            if data[0]['time'].timestamp() <= timestamp <= data[-1]['time'].timestamp():
                for idx in range(len(data)):
                    d = data[idx]['time'].timestamp()
                    if d >= timestamp:
                        return data[idx]['trade_id']
            else:
                if timestamp > data[0]['time'].timestamp():
                    lower = bound
                    bound = (upper + lower) // 2
                else:
                    upper = bound
                    bound = (upper + lower) // 2
            await asyncio.sleep(1 / self.request_limit)

    def _trade_normalize(self, symbol: str, data: dict) -> dict:
        return {
            'timestamp': data['time'].timestamp(),
            'symbol': symbol,
            'id': data['trade_id'],
            'feed': self.id,
            'side': SELL if data['side'] == 'buy' else BUY,
            'amount': Decimal(data['size']),
            'price': Decimal(data['price']),
        }

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        start, end = self._interval_normalize(start, end)
        if start:
            start_id = await self._date_to_trade(symbol, start)
            end_id = await self._date_to_trade(symbol, end)
            while True:
                limit = 100
                start_id += 100
                data = []

                if start_id > end_id:
                    limit = 100 - (start_id - end_id)
                    start_id = end_id
                if limit > 0:
                    data = await self._request('GET', f'/products/{symbol}/trades?after={start_id}&limit={limit}', retry_count=retry_count, retry_delay=retry_delay)
                    data = list(reversed(data))

                yield list(map(lambda x: self._trade_normalize(symbol, x), data))
                if start_id >= end_id:
                    break
                await asyncio.sleep(1 / self.request_limit)
        else:
            data = await self._request('GET', f"/products/{symbol}/trades", retry_count=retry_count, retry_delay=retry_delay)
            yield [self._trade_normalize(symbol, d) for d in data]

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        data = await self._request('GET', f'/products/{symbol}/ticker', retry_count=retry_count, retry_delay=retry_delay)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
                }

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        data = await self._request('GET', f'/products/{symbol}/book?level=2', retry_count=retry_count, retry_delay=retry_delay)
        ret = OrderBook(self.id, symbol)
        ret.book.bids = {Decimal(u[0]): Decimal(u[1]) for u in data['bids']}
        ret.book.asks = {Decimal(u[0]): Decimal(u[1]) for u in data['asks']}
        return ret

    async def l3_book(self, symbol: str, retry_count=1, retry_delay=60):
        data = await self._request('GET', f'/products/{symbol}/book?level=3', retry_count=retry_count, retry_delay=retry_delay)
        ret = OrderBook(self.id, symbol)

        for side in ('bids', 'asks'):
            for price, size, order_id in data[side]:
                price = Decimal(price)
                size = Decimal(size)
                if price in ret.book[side]:
                    ret.book[side][price][order_id] = size
                else:
                    ret.book[side][price] = {order_id: size}
        return ret

    async def balances(self):
        data = await self._request('GET', "/accounts", auth=True)
        return {
            entry['currency']: {
                'total': Decimal(entry['balance']),
                'available': Decimal(entry['available'])
            }
            for entry in data
        }

    async def orders(self):
        data = await self._request("GET", "/orders", auth=True)
        return [self._order_status(order) for order in data]

    async def order_status(self, order_id: str):
        order = await self._request("GET", f"/orders/{order_id}", auth=True)
        return self._order_status(order)

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
        ot = self.normalize_order_options(order_type)
        if ot == MARKET and price:
            raise ValueError('Cannot specify price on a market order')
        if ot == LIMIT and not price:
            raise ValueError('Must specify price on a limit order')

        body = {
            'product_id': symbol,
            'side': 'buy' if BUY else SELL,
            'size': str(amount),
            'type': ot
        }

        if price:
            body['price'] = str(price)
        if client_order_id:
            body['client_oid'] = client_order_id
        if options:
            _ = [body.update(self.normalize_order_options(o)) for o in options]
        data = await self._request('POST', '/orders', auth=True, body=body)
        return self._order_status(data)

    async def cancel_order(self, order_id: str):
        order = await self.order_status(order_id)
        data = await self._request("DELETE", f"/orders/{order_id}", auth=True)
        if data[0] == order['order_id']:
            order['status'] = CANCELLED
            return order
        return data

    async def trade_history(self, symbol: str, start=None, end=None):
        data = await self._request("GET", f"/orders?product_id={symbol}&status=done", auth=True)
        return [
            {
                'order_id': order['id'],
                'trade_id': order['id'],
                'side': BUY if order['side'] == 'buy' else SELL,
                'price': Decimal(order['executed_value']) / Decimal(order['filled_size']),
                'amount': Decimal(order['filled_size']),
                'timestamp': order['done_at'].timestamp(),
                'fee_amount': Decimal(order['fill_fees']),
                'fee_currency': symbol.split('-')[1]
            }
            for order in data
        ]

    def _candle_normalize(self, symbol: str, data: list, interval: str) -> dict:
        return Candle(
            self.id,
            symbol,
            data[0],
            data[0] + timedelta_str_to_sec(interval),
            interval,
            None,
            Decimal(data[3]),
            Decimal(data[4]),
            Decimal(data[2]),
            Decimal(data[1]),
            Decimal(data[5]),
            True,
            data[0],
            raw=data
        )

    def _to_isoformat(self, timestamp):
        """Required as cryptostore doesnt allow +00:00 for UTC requires Z explicitly.
        """
        return dt.utcfromtimestamp(timestamp).isoformat()

    async def candles(self, symbol: str, start: Optional[Union[str, dt, float]] = None, end: Optional[Union[str, dt, float]] = None, interval: Optional[str] = '1m', retry_count=1, retry_delay=60):
        """
        Historic rate OHLC candles
        [
            [ time, low, high, open, close, volume ],
            [ 1415398768, 0.32, 4.2, 0.35, 4.2, 12.3 ],
            ...
        ]

        symbol: str
            the symbol to query data for e.g. BTC-USD
        start: str, dt, float
            the start time (optional)
        end:str, dt, float
            the end time (optional)
        interval:
            string corresponding to the interval (1m, 5m, etc)
        """
        limit = 300  # return max of 300 rows per request
        valid_intervals = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600, '6h': 21600, '1d': 86400}
        assert interval in list(valid_intervals.keys()), f'Interval must be one of {", ".join(list(valid_intervals.keys()))}'

        start, end = self._interval_normalize(start, end)
        if start:
            start_id = start
            end_id_max = end

            LOG.debug(f"candles - stepping through {symbol} ({start}, {end})")
            while True:
                end_id = start_id + (limit - 1) * valid_intervals[interval]
                if end_id > end_id_max:
                    end_id = end_id_max
                if start_id > end_id_max:
                    break

                url = f'/products/{symbol}/candles?granularity={valid_intervals[interval]}&start={self._to_isoformat(start_id)}&end={self._to_isoformat(end_id)}'
                data = await self._request('GET', url, retry_count=retry_count, retry_delay=retry_delay)
                data = list(reversed(data))
                yield list(map(lambda x: self._candle_normalize(symbol, x, interval), data))
                await asyncio.sleep(1 / self.request_limit)
                start_id = end_id + valid_intervals[interval]
        else:
            data = await self._request('GET', f"/products/{symbol}/candles?granularity={valid_intervals[interval]}", retry_count=retry_count, retry_delay=retry_delay)
            yield [self._candle_normalize(symbol, d, interval) for d in data]
