import os
from functools import wraps
from time import sleep

import requests
import yaml

from cryptofeed.log import get_logger


LOG = get_logger('rest', 'rest.log')


def request_retry(exchange, retry, retry_wait):
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

    def handle_error(self, resp, log):
        if resp.status_code != 200:
            log.error("%s: Status code %d", self.ID, resp.status_code)
            log.error("%s: Headers: %s", self.ID, resp.headers)
            log.error("%s: Resp: %s", self.ID, resp.text)
            resp.raise_for_status()

    def trades(self, *args, **kwargs):
        raise NotImplementedError

    def funding(self, *args, **kwargs):
        raise NotImplementedError

    def place_order(self):
        raise NotImplementedError

    def cancel_order(self, order_id):
        raise NotImplementedError

    def __getitem__(self, key):
        if key == 'trades':
            return self.trades
        elif key == 'funding':
            return self.funding
