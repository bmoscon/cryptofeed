'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from functools import wraps
from time import sleep

import pandas as pd
import requests

from cryptofeed.log import get_logger
from cryptofeed.config import Config


def request_retry(exchange, retry, retry_wait, LOG):
    """
    decorator to retry request
    """
    def wrap(f):
        @wraps(f)
        def wrapped_f(*args, **kwargs):
            retry_count = retry
            while True:
                try:
                    return f(*args, **kwargs)
                except TimeoutError as e:
                    LOG.warning("%s: Timeout - %s", exchange, e)
                    if retry_count is not None:
                        if retry_count == 0:
                            raise
                        else:
                            retry_count -= 1
                    sleep(retry_wait)
                    continue
                except requests.exceptions.ConnectionError as e:
                    LOG.warning("%s: Connection error - %s", exchange, e)
                    if retry_count is not None:
                        if retry_count == 0:
                            raise
                        else:
                            retry_count -= 1
                    sleep(retry_wait)
                    continue
        return wrapped_f
    return wrap


class RestAPI:
    id = 'NotImplemented'

    def __init__(self, config=None, sandbox=False, subaccount=None):
        self.config = Config(config=config)
        self.log = get_logger('cryptofeed.rest', self.config.rest.log.filename, self.config.rest.log.level)
        self.sandbox = sandbox
        
        keys = self.config[self.id.lower()] if subaccount is None else self.config[self.id.lower()][subaccount]
        self.key_id = keys.key_id
        self.key_secret = keys.key_secret
        self.key_passphrase = keys.key_passphrase
        self.account_name = keys.account_name

    @staticmethod
    def _timestamp(ts):
        if isinstance(ts, (float, int)):
            return pd.to_datetime(ts, unit='s')
        return pd.Timestamp(ts)

    def _handle_error(self, resp):
        if resp.status_code != 200:
            self.log.error("%s: Status code %d for URL %s", self.id, resp.status_code, resp.url)
            self.log.error("%s: Headers: %s", self.id, resp.headers)
            self.log.error("%s: Resp: %s", self.id, resp.text)
            resp.raise_for_status()

    # public / non account specific
    def ticker(self, symbol: str, retry=None, retry_wait=10):
        raise NotImplementedError

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=0):
        raise NotImplementedError

    def funding(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    def l3_book(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    # account specific
    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        raise NotImplementedError

    def cancel_order(self, order_id: str):
        raise NotImplementedError

    def orders(self, sumbol: str = None):
        """
        Return outstanding orders
        """
        raise NotImplementedError

    def order_status(self, order_id: str):
        """
        Look up status of an order by id
        """
        raise NotImplementedError

    def trade_history(self, symbol: str = None, start=None, end=None):
        """
        Executed trade history
        """
        raise NotImplementedError

    def balances(self):
        raise NotImplementedError

    def positions(self, **kwargs):
        raise NotImplementedError

    def ledger(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        """
        Executed trade history
        """
        raise NotImplementedError

    def __getitem__(self, key):
        if key == 'trades':
            return self.trades
        elif key == 'funding':
            return self.funding
        elif key == 'l2_book':
            return self.l2_book
        elif key == 'l3_book':
            return self.l3_book
        elif key == 'ticker':
            return self.ticker
