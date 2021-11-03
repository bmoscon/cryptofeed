'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import BALANCES, BUY, CANCELLED, CANCEL_ORDER, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, L2_BOOK, LIMIT, MAKER_OR_CANCEL, OPEN, ORDER_STATUS, PARTIAL, PLACE_ORDER, SELL, TICKER, TRADES, TRADE_HISTORY
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


class GeminiRestMixin(RestExchange):
    api = "https://api.gemini.com"
    sandbox_api = "https://api.sandbox.gemini.com"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    order_options = {
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

    async def _get(self, command: str, retry_count, retry_delay, params=''):
        api = self.api if not self.sandbox else self.sandbox_api
        resp = await self.http_conn.read(f"{api}{command}{params}", retry_count=retry_count, retry_delay=retry_delay)
        return json.loads(resp, parse_float=Decimal)

    async def _post(self, command: str, payload=None):
        headers = self.generate_token(command, payload=payload)

        headers['Content-Type'] = "text/plain"
        headers['Content-Length'] = "0"
        headers['Cache-Control'] = "no-cache"

        api = self.api if not self.sandbox else self.sandbox_api
        api = f"{api}{command}"

        resp = await self.http_conn.write(api, header=headers)
        return json.loads(resp, parse_float=Decimal)

    # Public Routes
    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get(f"/v1/pubticker/{sym}", retry_count, retry_delay)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data['bid']),
                'ask': Decimal(data['ask'])
                }

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        ret = OrderBook(self.id, symbol)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get(f"/v1/book/{sym}", retry_count, retry_delay)
        ret.book.bids = {Decimal(u['price']): Decimal(u['amount']) for u in data['bids']}
        ret.book.asks = {Decimal(u['price']): Decimal(u['amount']) for u in data['asks']}
        return ret

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)
        params = "&limit_trades=500"
        if start:
            end_ts = int(end * 1000)
            params += f"&since={int(start * 1000)}"

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
            data = reversed(await self._get(f"/v1/trades/{sym}?", retry_count, retry_delay, params=params))
            if end:
                data = [_trade_normalize(d) for d in data if d['timestampms'] <= end_ts]
            else:
                data = [_trade_normalize(d) for d in data]
            yield data

            if start:
                params['since'] = int(data[-1]['timestamp'] * 1000) + 1
            if len(data) < 500 or not start:
                break
            await asyncio.sleep(1 / self.request_limit)

    # Trading APIs
    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, client_order_id=None, options=None):
        if not price:
            raise ValueError('Gemini only supports limit orders, must specify price')
        ot = self.normalize_order_options(order_type)
        sym = self.std_symbol_to_exchange_symbol(symbol)

        parameters = {
            'type': ot,
            'symbol': sym,
            'side': side,
            'amount': str(amount),
            'price': str(price),
            'options': [self.normalize_order_options(o) for o in options] if options else []
        }

        if client_order_id:
            parameters['client_order_id'] = client_order_id

        data = await self._post("/v1/order/new", parameters)
        return await self._order_status(data)

    async def cancel_order(self, order_id: str):
        data = await self._post("/v1/order/cancel", {'order_id': int(order_id)})
        return await self._order_status(data)

    async def order_status(self, order_id: str):
        data = await self._post("/v1/order/status", {'order_id': int(order_id)})
        return await self._order_status(data)

    async def orders(self):
        data = await self._post("/v1/orders")
        return [await self._order_status(d) for d in data]

    async def trade_history(self, symbol: str, start=None, end=None):
        sym = self.std_symbol_to_exchange_symbol(symbol)

        params = {
            'symbol': sym,
            'limit_trades': 500
        }
        if start:
            params['timestamp'] = self._datetime_normalize(start) * 1000

        data = await self._post("/v1/mytrades", params)
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

    async def balances(self):
        data = await self._post("/v1/balances")
        return {
            entry['currency']: {
                'total': Decimal(entry['amount']),
                'available': Decimal(entry['available'])
            } for entry in data}
