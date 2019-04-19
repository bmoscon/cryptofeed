'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
import hashlib
import hmac
import requests
import urllib
import base64
import logging
import calendar
from decimal import Decimal

import pandas as pd
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import KRAKEN, SELL, BUY, BID, ASK
from cryptofeed.standards import pair_std_to_exchange, feed_to_exchange


LOG = logging.getLogger('rest')


class Kraken(API):
    ID = KRAKEN

    api = "https://api.kraken.com/0"

    def _post_public(self, command: str, payload=None, retry=None, retry_wait=0):
        url = f"{self.api}{command}"

        @request_retry(self.ID, retry, retry_wait)
        def helper():
            resp = requests.post(url, data={} if not payload else payload)
            self._handle_error(resp, LOG)
            return resp.json()
        return helper()

    def _post_private(self, command: str, payload=None):
        # API-Key = API key
        # API-Sign = Message signature using HMAC-SHA512 of (URI path + SHA256(nonce + POST data)) and base64 decoded secret API key
        if payload is None:
            payload = {}
        payload['nonce'] = int(time.time() * 1000)

        urlpath = f'/0{command}'

        postdata = urllib.parse.urlencode(payload)

        # Unicode-objects must be encoded before hashing
        encoded = (str(payload['nonce']) + postdata).encode('utf8')
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        signature = hmac.new(base64.b64decode(self.key_secret),
                             message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        headers = {
            'API-Key': self.key_id,
            'API-Sign': sigdigest.decode()
        }

        resp = requests.post(f"{self.api}{command}", data=payload, headers=headers)
        self._handle_error(resp, LOG)

        return resp.json()

    # public API
    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID).replace("/", "")
        data = self._post_public(f"/public/Ticker", payload={'pair': sym}, retry=retry, retry_wait=retry_wait)

        data = data['result']
        for _, val in data.items():
            return {'pair': symbol,
                    'feed': self.ID,
                    'bid': Decimal(val['b'][0]),
                    'ask': Decimal(val['a'][0])
                }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = pair_std_to_exchange(symbol, self.ID).replace("/", "")
        data = self._post_public("/public/Depth", {'pair': sym, 'count': 200}, retry=retry, retry_wait=retry_wait)
        for _, val in data['result'].items():
            return {
                BID: sd({
                    Decimal(u[0]): Decimal(u[1])
                    for u in val['bids']
                }),
                ASK: sd({
                    Decimal(u[0]): Decimal(u[1])
                    for u in val['asks']
                })
            }

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=10):
        if start:
            if not end:
                end = pd.Timestamp.utcnow()
            for data in self._historical_trades(symbol, start, end, retry, retry_wait):
                yield list(map(lambda x: self._trade_normalization(x, symbol), data['result'][next(iter(data['result']))]))
        else:
            sym = pair_std_to_exchange(symbol, self.ID).replace("/", "")
            data = self._post_public("/public/Trades", {'pair': sym}, retry=retry, retry_wait=retry_wait)
            yield [self._trade_normalization(d, symbol) for d in data]


    def _historical_trades(self, symbol, start_date, end_date, retry, retry_wait, freq='6H'):
        symbol = pair_std_to_exchange(symbol, self.ID).replace("/", "")

        @request_retry(self.ID, retry, retry_wait)
        def helper(start_date):
            endpoint = f"{self.api}/public/Trades?pair={symbol}&since={start_date}"
            return requests.get(endpoint)


        start_date = calendar.timegm(pd.Timestamp(start_date).timetuple()) * 1000000000
        end_date = calendar.timegm(pd.Timestamp(end_date).timetuple()) * 1000000000

        while start_date < end_date:
            r = helper(start_date)

            if r.status_code == 504 or r.status_code == 520:
                # cloudflare gateway timeout or other error
                time.sleep(60)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)

            data = r.json()
            if 'error' in data and data['error']:
                if data['error'] == ['EAPI:Rate limit exceeded']:
                    time.sleep(20)
                    continue
                else:
                    raise Exception(f"Error processing URL {r.url}: {data['error']}")

            yield data

            start_date = int(data['result']['last'])

    def _trade_normalization(self, trade: list, symbol: str) -> dict:
        """
        ['976.00000', '1.34379010', 1483270225.7744, 's', 'l', '']
        """
        return {
            'timestamp': trade[2],
            'pair': symbol,
            'id': None,
            'feed': self.ID,
            'side': SELL if trade[3] == 's' else BUY,
            'amount': trade[1],
            'price': trade[0]
        }

    # Private API
    def get_account_balance(self, payload=None):
        """
        Parameters:
            aclass = asset class (optional)
            asset = base asset used to determine balance (default = ZUSD
        """
        return self._post_private('/private/Balance', payload)

    def get_open_orders(self, payload=None):
        """
        Parameters:
            trades = whether or not to include trades in output (optional.  default = false)
            userref = restrict results to given user reference id (optional)
        """
        return self._post_private('/private/OpenOrders', payload)

    def get_closed_orders(self, payload=None):
        """
        Parameters:
            trades = whether or not to include trades in output (optional.  default = false)
            userref = restrict results to given user reference id (optional)
            start = starting unix timestamp or order tx id of results (optional.  exclusive)
            end = ending unix timestamp or order tx id of results (optional.  inclusive)
            ofs = result offset
            closetime = which time to use (optional)
        """
        return self._post_private('/private/ClosedOrders', payload)

    def query_orders_info(self, payload=None):
        """
        Parameters:
            txid = comma delimited list of transaction ids to query info about (20 maximum)
            trades = whether or not to include trades in output (optional.  default = false)
            userref = restrict results to given user reference id (optional)
        """
        return self._post_private('/private/QueryOrders', payload)

    def get_trades_history(self, payload=None):
        """
        Parameters:
            type = type of trade (optional)
                all = all types (default)
                any position = any position (open or closed)
                closed position = positions that have been closed
                closing position = any trade closing all or part of a position
                no position = non-positional trades
            trades = whether or not to include trades related to position in output (optional.  default = false)
            start = starting unix timestamp or trade tx id of results (optional.  exclusive)
            end = ending unix timestamp or trade tx id of results (optional.  inclusive)
            ofs = result offset
        """
        return self._post_private('/private/TradesHistory', payload)

    def query_trades_info(self, payload: dict):
        """
        Parameters:
            txid = comma delimited list of transaction ids to query info about (20 maximum)
            trades = whether or not to include trades related to position in output (optional.  default = false)
        """
        return self._post_private('/private/QueryTrades', payload)

    def get_open_positions(self, payload: dict):
        """
        Parameters:
            txid = comma delimited list of transaction ids to restrict output to
            docalcs = whether or not to include profit/loss calculations (optional.  default = false)
        """
        return self._post_private('/private/OpenPositions', payload)

    def get_ledgers_info(self, payload=None):
        """
        Parameters:
            aclass = asset class (optional):
            currency (default)
        asset = comma delimited list of assets to restrict output to (optional.  default = all)
        type = type of ledger to retrieve (optional):
            all (default)
            deposit
            withdrawal
            trade
            margin
        start = starting unix timestamp or ledger id of results (optional.  exclusive)
        end = ending unix timestamp or ledger id of results (optional.  inclusive)
        ofs = result offset
        """
        return self._post_private('/private/Ledgers', payload)

    def query_ledgers(self, payload: dict):
        """
        Parameters:
            id = comma delimited list of ledger ids to query info about (20 maximum)
        """
        return self._post_private('/private/QueryLedgers', payload)

    def get_trade_volume(self, payload=None):
        """
        Parameters:
            pair = comma delimited list of asset pairs to get fee info on (optional)
            fee-info = whether or not to include fee info in results (optional)
        """
        return self._post_private('/private/TradeVolume', payload)

    def place_order(self, pair: str, side: str, order_type: str, amount: str, price: str, start_time: str, expire_time: str):
        """
        Parameters:
            pair = asset pair
            type = type of order (buy/sell)
            ordertype = order type:
                market
                limit (price = limit price)
                stop-loss (price = stop loss price)
                take-profit (price = take profit price)
                stop-loss-profit (price = stop loss price, price2 = take profit price)
                stop-loss-profit-limit (price = stop loss price, price2 = take profit price)
                stop-loss-limit (price = stop loss trigger price, price2 = triggered limit price)
                take-profit-limit (price = take profit trigger price, price2 = triggered limit price)
                trailing-stop (price = trailing stop offset)
                trailing-stop-limit (price = trailing stop offset, price2 = triggered limit offset)
                stop-loss-and-limit (price = stop loss price, price2 = limit price)
                settle-position
            price = price (optional.  dependent upon ordertype)
            price2 = secondary price (optional.  dependent upon ordertype)
            volume = order volume in lots
            leverage = amount of leverage desired (optional.  default = none)
            oflags = comma delimited list of order flags (optional):
                viqc = volume in quote currency (not available for leveraged orders)
                fcib = prefer fee in base currency
                fciq = prefer fee in quote currency
                nompp = no market price protection
                post = post only order (available when ordertype = limit)
            starttm = scheduled start time (optional):
                0 = now (default)
                +<n> = schedule start time <n> seconds from now
                <n> = unix timestamp of start time
            expiretm = expiration time (optional):
                0 = no expiration (default)
                +<n> = expire <n> seconds from now
                <n> = unix timestamp of expiration time
            userref = user reference id.  32-bit signed number.  (optional)
            validate = validate inputs only.  do not submit order (optional)
        """

        ot = feed_to_exchange(self.ID, order_type)

        parameters = {
            'pair': pair,
            'type': side,
            'volume': amount
        }

        if price is not None:
            parameters['price'] = price

        if start_time is not None:
            parameters['starttm'] = start_time

        if expire_time is not None:
            parameters['expiretm'] = expire_time

        return self._post_private('/private/AddOrder', parameters)

    def cancel_order(self, order_id):
        return self._post_private('/private/CancelOrder', {'txid': order_id})
