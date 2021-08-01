'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from time import sleep
import logging

import requests
from sortedcontainers.sorteddict import SortedDict as sd
from yapic import json

from cryptofeed.auth.gemini import generate_token
from cryptofeed.defines import BALANCES, BID, ASK, BUY, CANCELLED, CANCEL_ORDER, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, L2_BOOK, LIMIT, MAKER_OR_CANCEL, OPEN, ORDER_STATUS, PARTIAL, PLACE_ORDER, SELL, TICKER, TRADES, TRADE_HISTORY
from cryptofeed.exchange import RestExchange
from cryptofeed.connection import request_retry


LOG = logging.getLogger('feedhandler')


class GeminiRestMixin(RestExchange):
    api = "https://api.gemini.com"
    sandbox_api = "https://api.sandbox.gemini.com"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    rest_options = {
        LIMIT: 'exchange limit',
        FILL_OR_KILL: 'fill-or-kill',
        IMMEDIATE_OR_CANCEL: 'immediate-or-cancel',
        MAKER_OR_CANCEL: 'maker-or-cancel',
    }

    def _order_status(self, data):
        status = PARTIAL
        if data['is_cancelled']:
            status = CANCELLED
        elif Decimal(data['remaining_amount']) == 0:
            status = FILLED
        elif Decimal(data['executed_amount']) == 0:
            status = OPEN

        price = Decimal(data['price']) if Decimal(data['avg_execution_price']) == 0 else Decimal(data['avg_execution_price'])
        return {
            'order_id': data['order_id'],
            'symbol': self.exchange_symbol_to_std_symbol(data['symbol'].upper()),  # Gemini uses lowercase symbols for REST and uppercase for WS
            'side': BUY if data['side'] == 'buy' else SELL,
            'order_type': LIMIT,
            'price': price,
            'total': Decimal(data['original_amount']),
            'executed': Decimal(data['executed_amount']),
            'pending': Decimal(data['remaining_amount']),
            'timestamp': data['timestampms'] / 1000,
            'order_status': status
        }

    def _get(self, command: str, retry, retry_wait, params=None):
        api = self.api if not self.sandbox else self.sandbox_api

        @request_retry(self.id, retry, retry_wait)
        def helper():
            resp = requests.get(f"{api}{command}", params=params)
            self._handle_error(resp)
            return json.loads(resp.text, parse_float=Decimal)
        return helper()

    def _post(self, command: str, payload=None):
        headers = generate_token(self.config.key_id, self.config.key_secret, command, account_name=self.config.account_name, payload=payload)

        headers['Content-Type'] = "text/plain"
        headers['Content-Length'] = "0"
        headers['Cache-Control'] = "no-cache"

        api = self.api if not self.sandbox else self.sandbox_api
        api = f"{api}{command}"

        resp = requests.post(api, headers=headers)
        self._handle_error(resp)

        return json.loads(resp.text, parse_float=Decimal)

    # Public Routes
    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/v1/pubticker/{sym}", retry, retry_wait)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = self._get(f"/v1/book/{sym}", retry, retry_wait)
        return {
            BID: sd({
                Decimal(u['price']): Decimal(u['amount'])
                for u in data['bids']
            }),
            ASK: sd({
                Decimal(u['price']): Decimal(u['amount'])
                for u in data['asks']
            })
        }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        params = {'limit_trades': 500}
        if start:
            params['since'] = int(self._datetime_normalize(start) * 1000)
        if end:
            end_ts = int(self._datetime_normalize(start) * 1000)

        def _trade_normalize(trade):
            return {
                'feed': self.id,
                'order_id': trade['tid'],
                'symbol': self.exchange_symbol_to_std_symbol(sym),
                'side': trade['type'],
                'amount': Decimal(trade['amount']),
                'price': Decimal(trade['price']),
                'timestamp': trade['timestampms'] / 1000.0
            }

        while True:
            data = reversed(self._get(f"/v1/trades/{sym}?", retry, retry_wait, params=params))
            if end:
                data = [_trade_normalize(d) for d in data if d['timestampms'] <= end_ts]
            else:
                data = [_trade_normalize(d) for d in data]
            yield data

            if start:
                params['since'] = int(data[-1]['timestamp'] * 1000) + 1
            if len(data) < 500:
                break
            if not start and not end:
                break
            # GEMINI rate limits to 120 requests a minute
            sleep(1 / self.request_limit)

    # Trading APIs
    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
        if not price:
            raise ValueError('Gemini only supports limit orders, must specify price')
        ot = self.order_options(order_type)
        sym = self.std_symbol_to_exchange_symbol(symbol)

        parameters = {
            'type': ot,
            'symbol': sym,
            'side': side,
            'amount': str(amount),
            'price': str(price),
            'options': [self.order_options(o) for o in options] if options else []
        }

        if client_order_id:
            parameters['client_order_id'] = client_order_id

        data = self._post("/v1/order/new", parameters)
        return self._order_status(data)

    def cancel_order(self, order_id: str):
        data = self._post("/v1/order/cancel", {'order_id': int(order_id)})
        return self._order_status(data)

    def order_status(self, order_id: str):
        data = self._post("/v1/order/status", {'order_id': int(order_id)})
        return self._order_status(data)

    def orders(self):
        data = self._post("/v1/orders")
        return [self._order_status(d) for d in data]

    def trade_history(self, symbol: str, start=None, end=None):
        sym = self.std_symbol_to_exchange_symbol(symbol)

        params = {
            'symbol': sym,
            'limit_trades': 500
        }
        if start:
            params['timestamp'] = self._datetime_normalize(start)

        data = self._post("/v1/mytrades", params)
        return [
            {
                'price': Decimal(trade['price']),
                'amount': Decimal(trade['amount']),
                'timestamp': trade['timestampms'] / 1000,
                'side': BUY if trade['type'].lower() == 'buy' else SELL,
                'fee_currency': trade['fee_currency'],
                'fee_amount': trade['fee_amount'],
                'trade_id': trade['tid'],
                'order_id': trade['order_id']
            }
            for trade in data
        ]

    def balances(self):
        data = self._post("/v1/balances")
        return {
            entry['currency']: {
                'total': Decimal(entry['amount']),
                'available': Decimal(entry['available'])
            } for entry in data}
