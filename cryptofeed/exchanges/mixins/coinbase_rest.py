'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
import hmac
import hashlib
from decimal import Decimal
import logging
import time
from datetime import datetime as dt
from typing import Optional, Union

import requests
from yapic import json
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.defines import ASK, BID, BUY, CANCELLED, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, MAKER_OR_CANCEL, MARKET, OPEN, PARTIAL, PENDING, SELL, TRADES, TICKER, L2_BOOK, L3_BOOK, ORDER_INFO, ORDER_STATUS, CANDLES, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY, LIMIT
from cryptofeed.exceptions import UnexpectedMessage
from cryptofeed.connection import request_retry
from cryptofeed.exchange import RestExchange


LOG = logging.getLogger('feedhandler')


class CoinbaseRestMixin(RestExchange):
    api = "https://api.pro.coinbase.com"
    sandbox_api = "https://api-public.sandbox.pro.coinbase.com"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, L3_BOOK, ORDER_INFO, ORDER_STATUS, CANDLES, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    rest_options = {
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

    def _request(self, method: str, endpoint: str, auth: bool = False, body=None, retry=None, retry_wait=0):
        api = self.sandbox_api if self.sandbox else self.api

        @request_retry(self.id, retry, retry_wait)
        def helper(verb, api, endpoint, body, auth):
            header = None
            if auth:
                header = self._generate_signature(endpoint, verb, body=json.dumps(body) if body else '')

            if method == "GET":
                return requests.get(f'{api}{endpoint}', headers=header)
            elif method == 'POST':
                return requests.post(f'{api}{endpoint}', json=body, headers=header)
            elif method == 'DELETE':
                return requests.delete(f'{api}{endpoint}', headers=header)

        return helper(method, api, endpoint, body, auth)

    def _date_to_trade(self, symbol: str, timestamp: float) -> int:
        """
        Coinbase uses trade ids to query historical trades, so
        need to search for the start date
        """
        upper = self._request('GET', f'/products/{symbol}/trades')
        upper = json.loads(upper.text, parse_float=Decimal)[0]['trade_id']
        lower = 0
        bound = (upper - lower) // 2
        while True:
            r = self._request('GET', f'/products/{symbol}/trades?after={bound}')
            if r.status_code == 429:
                time.sleep(10)
                continue
            elif r.status_code != 200:
                LOG.warning("Error %s: %s", r.status_code, r.text)
                time.sleep(60)
                continue
            data = json.loads(r.text, parse_float=Decimal)
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
            time.sleep(1 / self.request_limit)

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

    def trades(self, symbol: Union[str, dt, float], start=None, end=None, retry=None, retry_wait=10):
        if end and not start:
            start = '2014-12-01 00:00:00'
        if start:
            if not end:
                end = dt.now().timestamp()
            start_id = self._date_to_trade(symbol, self._datetime_normalize(start))
            end_id = self._date_to_trade(symbol, self._datetime_normalize(end))
            while True:
                limit = 100
                start_id += 100
                if start_id > end_id:
                    limit = 100 - (start_id - end_id)
                    start_id = end_id
                if limit > 0:
                    r = self._request('GET', f'/products/{symbol}/trades?after={start_id}&limit={limit}', retry=retry, retry_wait=retry_wait)
                    if r.status_code == 429:
                        time.sleep(10)
                        continue
                    elif r.status_code != 200:
                        LOG.warning("Error %s: %s", r.status_code, r.text)
                        time.sleep(60)
                        continue
                    data = json.loads(r.text, parse_float=Decimal)
                    try:
                        data = list(reversed(data))
                    except Exception:
                        LOG.warning("Error %s: %s", r.status_code, r.text)
                        time.sleep(60)
                        continue
                else:
                    break

                yield list(map(lambda x: self._trade_normalize(symbol, x), data))
                if start_id >= end_id:
                    break
        else:
            data = self._request('GET', f"/products/{symbol}/trades", retry=retry, retry_wait=retry_wait)
            data = json.loads(data.text, parse_float=Decimal)
            yield [self._trade_normalize(symbol, d) for d in data]

    def ticker(self, symbol: str, retry=None, retry_wait=10):
        data = self._request('GET', f'/products/{symbol}/ticker', retry=retry, retry_wait=retry_wait)
        self._handle_error(data)
        data = json.loads(data.text, parse_float=Decimal)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
                }

    def _book(self, symbol: str, level: int, retry, retry_wait):
        data = self._request('GET', f'/products/{symbol}/book?level={level}', retry=retry, retry_wait=retry_wait)
        return json.loads(data.text, parse_float=Decimal)

    def l2_book(self, symbol: str, retry=None, retry_wait=10):
        data = self._book(symbol, 2, retry, retry_wait)
        return {
            BID: sd({
                Decimal(u[0]): Decimal(u[1])
                for u in data['bids']
            }),
            ASK: sd({
                Decimal(u[0]): Decimal(u[1])
                for u in data['asks']
            })
        }

    def l3_book(self, symbol: str, retry=None, retry_wait=10):
        orders = self._book(symbol, 3, retry, retry_wait)
        ret = {BID: sd({}), ASK: sd({})}
        for side in (BID, ASK):
            for price, size, order_id in orders[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                if price in ret[side]:
                    ret[side][price][order_id] = size
                else:
                    ret[side][price] = {order_id: size}
        return ret

    def balances(self):
        resp = self._request('GET', "/accounts", auth=True)
        self._handle_error(resp)
        return {
            entry['currency']: {
                'total': Decimal(entry['balance']),
                'available': Decimal(entry['available'])
            }
            for entry in json.loads(resp.text, parse_float=Decimal)
        }

    def orders(self):
        endpoint = "/orders"
        data = self._request("GET", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
        return [self._order_status(order) for order in data]

    def order_status(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self._request("GET", endpoint, auth=True)
        order = json.loads(order.text, parse_float=Decimal)
        return self._order_status(order)

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
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
        resp = self._request('POST', '/orders', auth=True, body=body)
        return self._order_status(json.loads(resp.text, parse_float=Decimal))

    def cancel_order(self, order_id: str):
        endpoint = f"/orders/{order_id}"
        order = self.order_status(order_id)
        data = self._request("DELETE", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
        if data[0] == order['order_id']:
            order['status'] = CANCELLED
            return order
        return data

    def trade_history(self, symbol: str, start=None, end=None):
        endpoint = f"/orders?product_id={symbol}&status=done"
        data = self._request("GET", endpoint, auth=True)
        data = json.loads(data.text, parse_float=Decimal)
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

    def _candle_normalize(self, symbol: str, data: list) -> dict:
        candle_position_names = ('time', 'low', 'high', 'open', 'close', 'volume')
        res = {'symbol': symbol, 'feed': self.id}
        for i, name in enumerate(candle_position_names):
            if name == 'time':
                res['timestamp'] = data[i]
            else:
                res[name] = Decimal(data[i])
        return res

    def _to_isoformat(self, timestamp):
        """Required as cryptostore doesnt allow +00:00 for UTC requires Z explicitly.
        """
        return dt.utcfromtimestamp(timestamp).isoformat()

    def candles(self, symbol: str, start: Optional[Union[str, dt, float]] = None, end: Optional[Union[str, dt, float]] = None, granularity: Optional[Union[int]] = 3600, retry=None, retry_wait=10):
        """
        Historic rate OHLC candles
        [
            [ time, low, high, open, close, volume ],
            [ 1415398768, 0.32, 4.2, 0.35, 4.2, 12.3 ],
            ...
        ]
        Parameters
        ----------
        :param symbol: the symbol to query data for e.g. BTC-USD
        :param start: the start time (optional)
        :param end: the end time (optional)
        :param granularity: in seconds (int). This field must be one of the following values: {60, 300, 900, 3600, 21600, 86400}
        If data points are readily available, your response may contain as many as 300
        candles and some of those candles may precede your declared start value.

        The maximum number of data points for a single request is 300 candles.
        If your selection of start/end time and granularity will result in more than
        300 data points, your request will be rejected. If you wish to retrieve fine
        granularity data over a larger time range, you will need to make multiple
        requests with new start/end ranges
        """
        limit = 300  # return max of 300 rows per request
        assert granularity in {60, 300, 900, 3600, 21600, 86400}, 'Granularity must be in {60, 300, 900, 3600, 21600, 86400} as per https://docs.pro.coinbase.com/#get-historic-rates'

        if end and not start:
            start = '2014-12-01 00:00:00'
        if start:
            if not end:
                end = dt.now().timestamp()
            start_id = self._datetime_normalize(start)
            end_id_max = self._datetime_normalize(end)

            LOG.info(f"candles - stepping through {symbol} ({start}, {end})")
            while True:

                end_id = start_id + (limit - 1) * granularity
                if end_id > end_id_max:
                    end_id = end_id_max
                if start_id > end_id_max:
                    break

                url = f'/products/{symbol}/candles?granularity={granularity}&start={self._to_isoformat(start_id)}&end={self._to_isoformat(end_id)}'
                r = self._request('GET', url, retry=retry, retry_wait=retry_wait)
                if r.status_code == 429:
                    time.sleep(10)
                    continue
                elif r.status_code != 200:
                    LOG.warning("Error %s: %s", r.status_code, r.text)
                    time.sleep(60)
                    continue

                data = json.loads(r.text, parse_float=Decimal)

                try:
                    data = list(reversed(data))
                except Exception:
                    LOG.warning("Error %s: %s", r.status_code, r.text)
                    time.sleep(60)
                    continue
                yield list(map(lambda x: self._candle_normalize(symbol, x), data))
                time.sleep(1 / self.request_limit)
                start_id = end_id + granularity
        else:
            data = self._request('GET', f"/products/{symbol}/candles", retry=retry, retry_wait=retry_wait)
            data = json.loads(data.text, parse_float=Decimal)
            yield [self._candle_normalize(symbol, d) for d in data]
