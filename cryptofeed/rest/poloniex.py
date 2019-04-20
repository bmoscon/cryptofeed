'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from time import time
import hashlib
import hmac
import requests
import urllib
from decimal import Decimal
import logging

import pandas as pd
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import POLONIEX, BUY, SELL, BID, ASK
from cryptofeed.standards import pair_std_to_exchange, pair_exchange_to_std, normalize_trading_options


LOG = logging.getLogger('rest')


# API docs https://poloniex.com/support/api/
# 6 calls per second API limit
class Poloniex(API):
    ID = POLONIEX

    # for public_api add "public" to the url, for trading add "tradingApi" (example: https://poloniex.com/public)
    rest_api = "https://poloniex.com/"


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
        sign = hmac.new(bytes(self.key_secret, 'utf8'), paybytes, hashlib.sha512).hexdigest()

        headers = {
            "Key": self.key_id,
            "Sign": sign,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        resp = requests.post(f"{self.rest_api}tradingApi?command={command}", headers=headers, data=paybytes)
        self._handle_error(resp, LOG)

        return resp.json()

    # Public API Routes
    def ticker(self, symbol: str, retry=None, retry_wait=10):
        sym = pair_std_to_exchange(symbol, self.ID)
        data = self._get("returnTicker", retry=retry, retry_wait=retry_wait)
        return {'pair': symbol,
                'feed': self.ID,
                'bid': Decimal(data[sym]['lowestAsk']),
                'ask': Decimal(data[sym]['highestBid'])
            }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID)
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
            'timestamp': trade['date'],
            'pair': pair_exchange_to_std(symbol),
            'id': trade['tradeID'],
            'feed': self.ID,
            'side': BUY if trade['type'] == 'buy' else SELL,
            'amount': Decimal(trade['amount']),
            'price': Decimal(trade['rate'])
        }

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        symbol = pair_std_to_exchange(symbol, self.ID)

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
            } for coin in data }

    def orders(self, symbol=None):
        if not symbol:
            payload = {"currencyPair": "all"}
        else:
            payload = {"currencyPair": pair_std_to_exchange(symbol, self.ID)}
        data = self._post("returnOpenOrders", payload)
        if isinstance(data, dict):
            return {pair_exchange_to_std(key): val for key, val in data.items()}
        else:
            return data

    def trade_history(self, symbol=None, start=None, end=None):
        if not symbol:
            payload = {"currencyPair": "all"}
        else:
            payload = {'currencyPair': pair_std_to_exchange(symbol, self.ID)}
        if start:
            payload['start'] = API._timestamp(start).timestamp()
        if end:
            payload['end'] = API._timestamp(end).timestamp()

        payload['limit'] = 10000
        return self._post("returnTradeHistory", payload)

    def order_status(self, order_id: str):
        return self._post("returnOrderStatus", {int(order_id)})

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price: Decimal, options=None):
        # Poloniex only supports limit orders, so check the order type
        _ = normalize_trading_options(self.ID, order_type)
        parameters = {
            normalize_trading_options(self.ID, o): 1 for o in options
        }
        parameters['currencyPair'] = pair_std_to_exchange(symbol, self.ID)
        parameters['amount'] = str(amount)
        parameters['rate'] = str(price)

        endpoint = None
        if side == BUY:
            endpoint = 'buy'
        elif side == SELL:
            endpoint = 'sell'
        return self._post(endpoint, parameters)

    def cancel_order(self, order_id: str):
        return self._post("cancelOrder", {"orderNumber": int(order_id)})
