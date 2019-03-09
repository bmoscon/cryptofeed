import time
import hashlib
import hmac
import requests
import urllib
import base64
import logging
import calendar

import pandas as pd

from cryptofeed.rest.api import API, request_retry
from cryptofeed.defines import KRAKEN, SELL, BUY
from cryptofeed.standards import pair_std_to_exchange


LOG = logging.getLogger('rest')


class Kraken(API):
    ID = KRAKEN

    api = "https://api.kraken.com/0"

    def _post_public(self, command: str, payload=None):
        if payload is None:
            payload = {}
        url = "{}{}".format(self.api, command)

        resp = requests.post(url, data=payload)
        self.handle_error(resp, LOG)

        return resp.json()

    def _post_private(self, command: str, payload=None):
        # API-Key = API key
        # API-Sign = Message signature using HMAC-SHA512 of (URI path + SHA256(nonce + POST data)) and base64 decoded secret API key
        if payload is None:
            payload = {}
        payload['nonce'] = int(time.time() * 1000)

        urlpath = '{}{}'.format('/0', command)

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

        resp = requests.post("{}{}".format(self.api, command), data=payload, headers=headers)
        self.handle_error(resp, LOG)

        return resp.json()

    # public API
    def get_server_time(self):
        return self._post_public("/public/Time")

    def get_asset_info(self, payload=None):
        """
        Parameters (optional):
            asset: comma delimited list of asset types (currencies)
            aclass: asset class
        """
        return self._post_public("/public/Assets", payload)

    def get_tradeable_pairs(self, payload=None):
        """
        Parameters:
            info: info = all info (default), leverage = leverage info, fees = fees schedule, margin = margin info
            pair: comma delimited list of asset pairs
        """
        return self._post_public("/public/AssetPairs", payload)

    def get_ticker_info(self, payload: dict):
        """
        Parameters:
            pair: comma delimited list of asset pairs (required)
        """
        return self._post_public("/public/Ticker", payload)

    def get_ohlc_data(self, payload=None):
        """
        Parameters:
            pair = asset pair to get OHLC data for (required)
            interval = time frame interval in minutes (optional):
                1 (default), 5, 15, 30, 60, 240, 1440, 10080, 21600
            since = return committed OHLC data since given id (optional.  exclusive)
        """
        return self._post_public("/public/OHLC", payload)

    def get_order_book(self, payload=None):
        """
        Parameters:
            pair = asset pair to get market depth for
            count = maximum number of asks/bids (optional)
        """
        return self._post_public("/public/Depth", payload)

    def trades(self, symbol, start=None, end=None, retry=None, retry_wait=10):
        if start and end:
            for data in self._historical_trades(symbol, start, end, retry, retry_wait):
                yield list(map(lambda x: self._trade_normalization(x, symbol), data['result'][next(iter(data['result']))]))
        else:
            yield self._post_public("/public/Trades", {'pair': symbol})


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
                self.handle_error(r, LOG)

            data = r.json()
            if 'error' in data and data['error']:
                if data['error'] == ['EAPI:Rate limit exceeded']:
                    time.sleep(20)
                    continue
                else:
                    raise Exception("Error: {}".format(data['error']))

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

    def get_recent_spread_data(self, payload=None):
        """
        Parameters:
            pair = asset pair to get spread data for
            since = return spread data since given id (optional.  inclusive)
        """
        return self._post_public("/public/Spread", payload)

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

    def add_standard_order(self, payload: dict):
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
        return self._post_private('/private/AddOrder', payload)

    def cancel_order(self, order_id):
        return self._post_private('/private/CancelOrder', {'txid': order_id})
