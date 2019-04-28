'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
from functools import wraps
from time import sleep
import logging
from decimal import Decimal

import pandas as pd
import requests
import yaml

from cryptofeed.standards import load_exchange_pair_mapping

LOG = logging.getLogger('rest')

def request_retry(exchange, retry, retry_wait):
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


class API:
    ID = 'NotImplemented'

    def __init__(self, config, sandbox=False):
        self.mapped = False
        path = os.path.dirname(os.path.abspath(__file__))
        self.key_id, self.key_secret, self.key_passphrase = None, None, None
        self.sandbox = sandbox
        if not config:
            config = "config.yaml"

        try:
            with open(os.path.join(path, config), 'r') as fp:
                data = yaml.safe_load(fp)
                self.key_id = data[self.ID.lower()]['key_id']
                self.key_secret = data[self.ID.lower()]['key_secret']
                if 'key_passphrase' in data[self.ID.lower()]:
                    self.key_passphrase = data[self.ID.lower()]['key_passphrase']
        except (KeyError, FileNotFoundError, TypeError):
            pass

    @staticmethod
    def _timestamp(ts):
        if isinstance(ts, (float, int)):
            return pd.to_datetime(ts, unit='s')
        return pd.Timestamp(ts)

    def _handle_error(self, resp, log):
        if resp.status_code != 200:
            log.error("%s: Status code %d for URL %s", self.ID, resp.status_code, resp.url)
            log.error("%s: Headers: %s", self.ID, resp.headers)
            log.error("%s: Resp: %s", self.ID, resp.text)
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

    def orders(self):
        """
        Return outstanding orders
        """
        raise NotImplementedError

    def order_status(self, order_id: str):
        """
        Look up status of an order by id
        """
        raise NotImplementedError

    def trade_history(self, symbol: str, start=None, end=None):
        """
        Executed trade history
        """
        raise NotImplementedError

    def balances(self):
        raise NotImplementedError

    def __getitem__(self, key):
        if not self.mapped:
            try:
                load_exchange_pair_mapping(self.ID + 'REST')
            except KeyError:
                load_exchange_pair_mapping(self.ID)
            self.mapped = True
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
