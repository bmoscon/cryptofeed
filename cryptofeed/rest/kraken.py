'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
from cryptofeed.exceptions import UnsupportedSymbol
import hashlib
import hmac
import logging
import time
from typing import Dict
import urllib
from decimal import Decimal

import pandas as pd
import requests
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.defines import BID, ASK, BUY, CANCELLED, FILLED, KRAKEN, LIMIT, MARKET, OPEN, SELL
from cryptofeed.exchanges import Kraken as KrakenEx
from cryptofeed.rest.api import API, request_retry
from cryptofeed.standards import normalize_trading_options

LOG = logging.getLogger('rest')
RATE_LIMIT_SLEEP = 1


def kraken_rest_symbols() -> Dict[str, str]:
    return {normalized: exchange.replace("/", "") for normalized, exchange in KrakenEx.symbol_mapping().items()}


class Kraken(API):
    ID = KRAKEN
    api = "https://api.kraken.com/0"
    _normalized_symbol_mapping = kraken_rest_symbols()
    _exchange_symbol_mapping = {value: key for key, value in _normalized_symbol_mapping.items()}

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        try:
            return self._exchange_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.ID}')

    def std_symbol_to_exchange_symbol(self, symbol: str) -> str:
        try:
            return self._normalized_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.ID}')

    @staticmethod
    def _fix_currencies(currency: str):
        cur_map = {
            'XXBT': 'BTC',
            'XXDG': 'DOGE',
            'XXLM': 'XLM',
            'XXMR': 'XMR',
            'XXRP': 'XRP',
            'ZUSD': 'USD',
            'ZCAD': 'CAD',
            'ZGBP': 'GBP',
            'ZJPY': 'JPY'
        }
        if currency in cur_map:
            return cur_map[currency]
        return currency

    def _order_status(self, order_id: str, order: dict):
        if order['status'] == 'canceled':
            status = CANCELLED
        if order['status'] == 'open':
            status = OPEN
        if order['status'] == 'closed':
            status = FILLED

        return {
            'order_id': order_id,
            'symbol': self.exchange_symbol_to_std_symbol(order['descr']['pair']),
            'side': SELL if order['descr']['type'] == 'sell' else BUY,
            'order_type': LIMIT if order['descr']['ordertype'] == 'limit' else MARKET,
            'price': Decimal(order['descr']['price']),
            'total': Decimal(order['vol']),
            'executed': Decimal(order['vol_exec']),
            'pending': Decimal(order['vol']) - Decimal(order['vol_exec']),
            'timestamp': order['opentm'],
            'order_status': status
        }

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

        signature = hmac.new(base64.b64decode(self.config.key_secret),
                             message, hashlib.sha512)
        sigdigest = base64.b64encode(signature.digest())

        headers = {
            'API-Key': self.config.key_id,
            'API-Sign': sigdigest.decode()
        }

        resp = requests.post(f"{self.api}{command}", data=payload, headers=headers)
        self._handle_error(resp, LOG)

        return resp.json()

    # public API
    def ticker(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = self._post_public("/public/Ticker", payload={'pair': sym}, retry=retry, retry_wait=retry_wait)

        data = data['result']
        for _, val in data.items():
            return {'symbol': symbol,
                    'feed': self.ID,
                    'bid': Decimal(val['b'][0]),
                    'ask': Decimal(val['a'][0])
                    }

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        sym = self.std_symbol_to_exchange_symbol(symbol)
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
            sym = self.std_symbol_to_exchange_symbol(symbol)
            data = self._post_public("/public/Trades", {'pair': sym}, retry=retry, retry_wait=retry_wait)
            data = data['result']
            data = data[list(data.keys())[0]]
            yield [self._trade_normalization(d, symbol) for d in data]

    def _historical_trades(self, symbol, start_date, end_date, retry, retry_wait, freq='6H'):
        symbol = self.std_symbol_to_exchange_symbol(symbol)

        @request_retry(self.ID, retry, retry_wait)
        def helper(start_date):
            endpoint = f"{self.api}/public/Trades?symbol={symbol}&since={start_date}"
            return requests.get(endpoint)

        start_date = API._timestamp(start_date).timestamp() * 1000000000
        end_date = API._timestamp(end_date).timestamp() * 1000000000

        while start_date < end_date:
            r = helper(start_date)

            if r.status_code == 504 or r.status_code == 520:
                # cloudflare gateway timeout or other error
                time.sleep(60)
                continue
            elif r.status_code != 200:
                self._handle_error(r, LOG)
            else:
                time.sleep(RATE_LIMIT_SLEEP)

            data = r.json()
            if 'error' in data and data['error']:
                if data['error'] == ['EAPI:Rate limit exceeded']:
                    time.sleep(5)
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
            'symbol': symbol,
            'id': None,
            'feed': self.ID,
            'side': SELL if trade[3] == 's' else BUY,
            'amount': trade[1],
            'price': trade[0]
        }

    # Private API
    def balances(self):
        data = self._post_private('/private/Balance')
        if len(data['error']) != 0:
            return data
        return {
            Kraken._fix_currencies(currency): {
                'available': Decimal(value),
                'total': Decimal(value)
            }
            for currency, value in data['result'].items()
        }

    def orders(self):
        data = self._post_private('/private/OpenOrders', None)
        if len(data['error']) != 0:
            return data

        ret = []
        for _, orders in data['result'].items():
            for order_id, order in orders.items():
                ret.append(self._order_status(order_id, order))
        return ret

    def order_status(self, order_id: str):
        data = self._post_private('/private/QueryOrders', {'txid': order_id})
        if len(data['error']) != 0:
            return data

        for order_id, order in data['result'].items():
            return self._order_status(order_id, order)

    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, options=None):
        ot = normalize_trading_options(self.ID, order_type)

        parameters = {
            'pair': self.std_symbol_to_exchange_symbol(symbol),
            'type': 'buy' if side == BUY else 'sell',
            'volume': str(amount),
            'ordertype': ot
        }

        if price is not None:
            parameters['price'] = str(price)

        if options:
            parameters['oflags'] = ','.join([normalize_trading_options(self.ID, o) for o in options])

        data = self._post_private('/private/AddOrder', parameters)
        if len(data['error']) != 0:
            return data
        else:
            if len(data['result']['txid']) == 1:
                return self.order_status(data['result']['txid'][0])
            else:
                return [self.order_status(tx) for tx in data['result']['txid']]

    def cancel_order(self, order_id: str):
        data = self._post_private('/private/CancelOrder', {'txid': order_id})
        if len(data['error']) != 0:
            return data
        else:
            return self.order_status(order_id)

    def trade_history(self, symbol: str = None, start=None, end=None):
        params = {}

        if start:
            params['start'] = API._timestamp(start).timestamp()
        if end:
            params['end'] = API._timestamp(end).timestamp()

        data = self._post_private('/private/TradesHistory', params)
        if len(data['error']) != 0:
            return data

        ret = {}
        for trade_id, trade in data['result']['trades'].items():
            sym = self._convert_private_sym(trade['pair'])
            std_sym = self.exchange_symbol_to_std_symbol(sym)
            if symbol and self.exchange_symbol_to_std_symbol(sym) != symbol:
                continue
            # exception safety?
            ret[trade_id] = {
                'order_id': trade['ordertxid'],
                'trade_id': trade_id,
                'pair': std_sym,
                'price': Decimal(trade['price']),
                'amount': Decimal(trade['vol']),
                'timestamp': trade['time'],
                'side': SELL if trade['type'] == 'sell' else BUY,
                'fee_currency': symbol.split('-')[1] if symbol else std_sym.split('-')[1],
                'fee_amount': Decimal(trade['fee']),
                'raw': trade
            }
        return ret

    def ledger(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):

        params = {}
        if start:
            params['start'] = API._timestamp(start).timestamp()
        if end:
            params['end'] = API._timestamp(end).timestamp()
        if aclass:
            params['aclass'] = aclass
        if asset:
            params['asset'] = asset
        if ledger_type:
            params['type'] = ledger_type

        data = self._post_private('/private/Ledgers', params)
        if len(data['error']) != 0:
            return data

        ret = {}
        for ledger_id, ledger in data['result']['ledger'].items():
            sym = self._convert_private_sym(ledger['asset'])

            ret[ledger_id] = {
                'ref_id': ledger['refid'],
                'ledger_id': ledger_id,
                'type': ledger['type'],
                'sub_type': ledger['subtype'],
                'asset': sym,
                'asset_class': ledger['aclass'],
                'amount': Decimal(ledger['amount']),
                'balance': Decimal(ledger['balance']),
                'timestamp': ledger['time'],
                'fee_currency': sym,
                'fee_amount': Decimal(ledger['fee']),
                'raw': ledger
            }
        return ret

    def _convert_private_sym(self, sym):
        """
            XETHZGBP = > ETHGBP
            XETH => ETH
            ZGBP => GBP
        """
        cleansym = sym
        try:
            symlen = len(sym)
            if symlen == 8 or symlen == 9:
                cleansym = sym[1:4] + sym[5:]
            elif symlen == 4:
                cleansym = sym[1:]
        except Exception as ex:
            LOG.error(f"Couldnt convert private api symbol {sym} for {self.ID}", ex)
            pass
        return cleansym