'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import hashlib
import hmac
import urllib
from decimal import Decimal
import time
import logging

from yapic import json

from cryptofeed.defines import BALANCES, BUY, CANCELLED, CANCEL_ORDER, FILLED, FILL_OR_KILL, IMMEDIATE_OR_CANCEL, L2_BOOK, LIMIT, MAKER_OR_CANCEL, OPEN, ORDER_INFO, ORDER_STATUS, PARTIAL, PLACE_ORDER, SELL, TICKER, TRADES, TRADE_HISTORY
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class PoloniexRestMixin(RestExchange):
    api = "https://poloniex.com"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, ORDER_INFO, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, TRADE_HISTORY
    )
    order_options = {
        LIMIT: 'limit',
        FILL_OR_KILL: 'fillOrKill',
        IMMEDIATE_OR_CANCEL: 'immediateOrCancel',
        MAKER_OR_CANCEL: 'postOnly',
    }

    def _order_status(self, order, symbol=None):
        if symbol:
            order_id = order['orderNumber']
            data = order
        else:
            [(order_id, data)] = order.items()

        if 'status' in data:
            status = PARTIAL
            if data['status'] == 'Open':
                status = OPEN
        else:
            if data['startingAmount'] == data['amount']:
                status = OPEN
            else:
                status = PARTIAL

        return {
            'order_id': order_id,
            'symbol': symbol if symbol else self.exchange_symbol_to_std_symbol(data['currencyPair']),
            'side': BUY if data['type'] == 'buy' else SELL,
            'order_type': LIMIT,
            'price': Decimal(data['rate']),
            'total': Decimal(data['startingAmount']),
            'executed': Decimal(data['startingAmount']) - Decimal(data['amount']),
            'pending': Decimal(data['amount']),
            'timestamp': data['date'].timestamp(),
            'order_status': status
        }

    def _trade_status(self, trades, symbol: str, order_id: str, total: str):
        total = Decimal(total)
        side = None
        price = Decimal('0.0')
        amount = Decimal('0.0')

        for trade in trades:
            date = trade['date']
            side = BUY if trade['type'] == 'buy' else SELL
            price += Decimal(trade['rate']) * Decimal(trade['amount'])
            amount += Decimal(trade['amount'])

        price /= amount

        return {
            'order_id': order_id,
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'side': side,
            'order_type': LIMIT,
            'price': price,
            'total': total,
            'executed': amount,
            'pending': total - amount,
            'timestamp': date.timestamp(),
            'order_status': FILLED
        }

    async def _get(self, command: str, params='', retry_count=1, retry_delay=60):
        base_url = f"{self.api}/public?command={command}{params}"
        resp = await self.http_conn.read(base_url, retry_count=retry_count, retry_delay=retry_delay)
        return json.loads(resp, parse_float=Decimal)

    async def _post(self, command: str, payload=None):
        if not payload:
            payload = {}
        # need to sign the payload, referenced https://stackoverflow.com/questions/43559332/python-3-hash-hmac-sha512
        payload['command'] = command
        payload['nonce'] = int(time.time() * 1000)

        paybytes = urllib.parse.urlencode(payload).encode('utf8')
        sign = hmac.new(bytes(self.config.key_secret, 'utf8'), paybytes, hashlib.sha512).hexdigest()

        headers = {
            "Key": self.config.key_id,
            "Sign": sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        resp = await self.http_conn.write(f"{self.api}tradingApi?command={command}", header=headers, msg=paybytes)
        return json.loads(resp, parse_float=Decimal)

    # Public API Routes
    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get("returnTicker", retry_count=retry_count, retry_delay=retry_delay)
        return {'symbol': symbol,
                'feed': self.id,
                'bid': Decimal(data[sym]['lowestAsk']),
                'ask': Decimal(data[sym]['highestBid'])
                }

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        ret = OrderBook(self.id, symbol)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self._get("returnOrderBook", params=f"&currencyPair={sym}", retry_count=retry_count, retry_delay=retry_delay)
        ret.book.bids = {Decimal(u[0]): Decimal(u[1]) for u in data['bids']}
        ret.book.asks = {Decimal(u[0]): Decimal(u[1]) for u in data['asks']}
        return ret

    def _trade_normalize(self, trade, symbol):
        return {
            'timestamp': trade['date'].timestamp(),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['tradeID'],
            'feed': self.id,
            'side': BUY if trade['type'] == 'buy' else SELL,
            'amount': Decimal(trade['amount']),
            'price': Decimal(trade['rate'])
        }

    async def trades(self, symbol, start=None, end=None, retry_count=1, retry_delay=60):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)

        if not start and not end:
            data = await self._get("returnTradeHistory", params=f"&currencyPair={symbol}", retry_count=retry_count, retry_delay=retry_delay)
            data.reverse()
            yield [self._trade_normalize(x, symbol) for x in data]

        else:
            s = start
            e = start + 21600
            while True:
                if e > end:
                    e = end

                data = await self._get("returnTradeHistory", params=f"&currencyPair={symbol}&start={start}&end={end}", retry_count=retry_count, retry_delay=retry_delay)
                data.reverse()
                yield list(map(lambda x: self._trade_normalize(x, symbol), data))

                s = e
                e += 21600
                if s >= end:
                    break
                await asyncio.sleep(1 / self.request_limit)

    # Trading API Routes
    async def balances(self):
        data = await self._post("returnCompleteBalances")
        return {
            coin: {
                'total': Decimal(data[coin]['available']) + Decimal(data[coin]['onOrders']),
                'available': Decimal(data[coin]['available'])
            } for coin in data}

    async def orders(self):
        payload = {"currencyPair": "all"}
        data = await self._post("returnOpenOrders", payload)
        if isinstance(data, dict):
            data = {self.exchange_symbol_to_std_symbol(key): val for key, val in data.items()}

        ret = []
        for symbol in data:
            if data[symbol] == []:
                continue
            for order in data[symbol]:
                ret.append(self._order_status(order, symbol=symbol))
        return ret

    async def trade_history(self, symbol: str, start=None, end=None):
        payload = {'currencyPair': self.std_symbol_to_exchange_symbol(symbol)}

        if start:
            payload['start'] = self._timestamp(start).timestamp()
        if end:
            payload['end'] = self._timestamp(end).timestamp()

        payload['limit'] = 10000
        data = self._post("returnTradeHistory", payload)
        ret = []
        for trade in data:
            ret.append({
                'price': Decimal(trade['rate']),
                'amount': Decimal(trade['amount']),
                'timestamp': trade['date'].timestamp(),
                'side': BUY if trade['type'] == 'buy' else SELL,
                'fee_currency': symbol.split('-')[1],
                'fee_amount': Decimal(trade['fee']),
                'trade_id': trade['tradeID'],
                'order_id': trade['orderNumber']
            })
        return ret

    async def order_status(self, order_id: str):
        data = await self._post("returnOrderStatus", {'orderNumber': order_id})
        if 'error' in data:
            return {'error': data['error']}
        elif 'error' in data['result']:
            return {'error': data['result']['error']}
        return self._order_status(data['result'])

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, options=None):
        if not price:
            raise ValueError('Poloniex only supports limit orders, must specify price')
        # Poloniex only supports limit orders, so check the order type
        _ = self.normalize_order_options(self.id, order_type)
        parameters = {}
        if options:
            parameters = {
                self.normalize_order_options(self.id, o): 1 for o in options
            }
        parameters['currencyPair'] = self.std_symbol_to_exchange_symbol(symbol)
        parameters['amount'] = str(amount)
        parameters['rate'] = str(price)

        endpoint = None
        if side == BUY:
            endpoint = 'buy'
        elif side == SELL:
            endpoint = 'sell'

        data = await self._post(endpoint, parameters)
        order = await self.order_status(data['orderNumber'])

        if 'error' not in order:
            if len(data['resultingTrades']) == 0:
                return order
            else:
                return self._trade_status(data['resultingTrades'], symbol, data['orderNumber'], amount)
        return data

    async def cancel_order(self, order_id: str):
        order = await self.order_status(order_id)
        data = await self._post("cancelOrder", {"orderNumber": int(order_id)})
        if 'error' in data:
            return {'error': data['error']}
        if 'message' in data and 'canceled' in data['message']:
            order['status'] = CANCELLED
            return order
        else:
            return data
