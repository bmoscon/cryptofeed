'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import logging
import urllib
from decimal import Decimal
from time import time

import pandas as pd
import requests
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, CANCELLED, FILLED, LIMIT, OPEN, PARTIAL, POLONIEX, SELL
from cryptofeed.exchanges import Poloniex as PoloniexEx
from cryptofeed.rest.api import API, request_retry
from cryptofeed.standards import normalize_trading_options


LOG = logging.getLogger('rest')


# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class Poloniex(API):
    ID = POLONIEX
    info = PoloniexEx()

    # for public_api add "public" to the url, for trading add "tradingApi" (example: https://poloniex.com/public)
    rest_api = "https://poloniex.com/"

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
            'symbol': symbol if symbol else self.info.exchange_symbol_to_std_symbol(data['currencyPair']),
            'side': BUY if data['type'] == 'buy' else SELL,
            'order_type': LIMIT,
            'price': Decimal(data['rate']),
            'total': Decimal(data['startingAmount']),
            'executed': Decimal(data['startingAmount']) - Decimal(data['amount']),
            'pending': Decimal(data['amount']),
            'timestamp': pd.Timestamp(data['date']).timestamp(),
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
            'symbol': self.info.exchange_symbol_to_std_symbol(symbol),
            'side': side,
            'order_type': LIMIT,
            'price': price,
            'total': total,
            'executed': amount,
            'pending': total - amount,
            'timestamp': pd.Timestamp(date).timestamp(),
            'order_status': FILLED
        }

    def _get(self, command: str, options=None, retry=None, retry_wait=0):
        base_url = f"{self.rest_api}public?command={command}"

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            resp = requests.get(base_url, params=options)
            self._handle_error(resp, LOG)
            return resp.json()
        return helper()

    def _post(self, command: str, payload=None):
        if not payload:
            payload = {}
        # need to sign the payload, referenced https://stackoverflow.com/questions/43559332/python-3-hash-hmac-sha512
        payload['command'] = command
        payload['nonce'] = int(time() * 1000)

        paybytes = urllib.parse.urlencode(payload).encode('utf8')
        sign = hmac.new(bytes(self.config.key_secret, 'utf8'), paybytes, hashlib.sha512).hexdigest()

        headers = {
            "Key": self.config.key_id,
            "Sign": sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        resp = requests.post(f"{self.rest_api}tradingApi?command={command}", headers=headers, data=paybytes)
        self._handle_error(resp, LOG)

        return resp.json()

    # Public API Routes
    def ticker(self, symbol: str, retry=None, retry_wait=10):
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        data = self._get("returnTicker", retry=retry, retry_wait=retry_wait)
        return {'symbol': symbol,
                'feed': self.ID,
                'bid': Decimal(data[sym]['lowestAsk']),
                'ask': Decimal(data[sym]['highestBid'])
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = self.info.std_symbol_to_exchange_symbol(symbol)
        data = self._get("returnOrderBook", {'currencyPair': sym}, retry=retry, retry_wait=retry_wait)
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

    def _trade_normalize(self, trade, symbol):
        return {
            'timestamp': pd.Timestamp(trade['date']).timestamp(),
            'symbol': self.info.exchange_symbol_to_std_symbol(symbol),
            'id': trade['tradeID'],
            'feed': self.ID,
            'side': BUY if trade['type'] == 'buy' else SELL,
            'amount': Decimal(trade['amount']),
            'price': Decimal(trade['rate'])
        }

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        symbol = self.info.std_symbol_to_exchange_symbol(symbol)

        @request_retry(self.ID, retry, retry_wait)
        def helper(s=None, e=None):
            data = self._get("returnTradeHistory", {'currencyPair': symbol, 'start': s, 'end': e})
            data.reverse()
            return data

        if not start:
            yield map(lambda x: self._trade_normalize(x, symbol), helper())

        else:
            if not end:
                end = pd.Timestamp.utcnow()
            start = API._timestamp(start)
            end = API._timestamp(end) - pd.Timedelta(nanoseconds=1)

            start = int(start.timestamp())
            end = int(end.timestamp())

            s = start
            e = start + 21600
            while True:
                if e > end:
                    e = end

                yield map(lambda x: self._trade_normalize(x, symbol), helper(s=s, e=e))

                s = e
                e += 21600
                if s >= end:
                    break

    # Trading API Routes
    def balances(self):
        data = self._post("returnCompleteBalances")
        return {
            coin: {
                'total': Decimal(data[coin]['available']) + Decimal(data[coin]['onOrders']),
                'available': Decimal(data[coin]['available'])
            } for coin in data}

    def orders(self):
        payload = {"currencyPair": "all"}
        data = self._post("returnOpenOrders", payload)
        if isinstance(data, dict):
            data = {self.exchange_symbol_to_std_symbol(key): val for key, val in data.items()}

        ret = []
        for symbol in data:
            if data[symbol] == []:
                continue
            for order in data[symbol]:
                ret.append(self._order_status(order, symbol=symbol))
        return ret

    def trade_history(self, symbol: str, start=None, end=None):
        payload = {'currencyPair': self.info.std_symbol_to_exchange_symbol(symbol)}

        if start:
            payload['start'] = API._timestamp(start).timestamp()
        if end:
            payload['end'] = API._timestamp(end).timestamp()

        payload['limit'] = 10000
        data = self._post("returnTradeHistory", payload)
        ret = []
        for trade in data:
            ret.append({
                'price': Decimal(trade['rate']),
                'amount': Decimal(trade['amount']),
                'timestamp': pd.Timestamp(trade['date']).timestamp(),
                'side': BUY if trade['type'] == 'buy' else SELL,
                'fee_currency': symbol.split('-')[1],
                'fee_amount': Decimal(trade['fee']),
                'trade_id': trade['tradeID'],
                'order_id': trade['orderNumber']
            })
        return ret

    def order_status(self, order_id: str):
        data = self._post("returnOrderStatus", {'orderNumber': order_id})
        if 'error' in data:
            return {'error': data['error']}
        elif 'error' in data['result']:
            return {'error': data['result']['error']}
        return self._order_status(data['result'])

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, options=None):
        if not price:
            raise ValueError('Poloniex only supports limit orders, must specify price')
        # Poloniex only supports limit orders, so check the order type
        _ = normalize_trading_options(self.ID, order_type)
        parameters = {}
        if options:
            parameters = {
                normalize_trading_options(self.ID, o): 1 for o in options
            }
        parameters['currencyPair'] = self.info.std_symbol_to_exchange_symbol(symbol)
        parameters['amount'] = str(amount)
        parameters['rate'] = str(price)

        endpoint = None
        if side == BUY:
            endpoint = 'buy'
        elif side == SELL:
            endpoint = 'sell'

        data = self._post(endpoint, parameters)
        order = self.order_status(data['orderNumber'])

        if 'error' not in order:
            if len(data['resultingTrades']) == 0:
                return order
            else:
                return self._trade_status(data['resultingTrades'], symbol, data['orderNumber'], amount)
        return data

    def cancel_order(self, order_id: str):
        order = self.order_status(order_id)
        data = self._post("cancelOrder", {"orderNumber": int(order_id)})
        if 'error' in data:
            return {'error': data['error']}
        if 'message' in data and 'canceled' in data['message']:
            order['status'] = CANCELLED
            return order
        else:
            return data
