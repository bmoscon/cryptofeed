import os
from functools import wraps
from time import sleep

import requests
import yaml

from cryptofeed.log import get_logger


LOG = get_logger('rest', 'rest.log')


def request_retry(ID, retry=None, retry_wait=10):
    """
    exception handler decorator that handles retries for requests
    """
    def _req_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            while True:
                try:
                    return f(*args, **kwargs)
                except TimeoutError as e:
                    LOG.warning("%s: Timeout - %s", ID, e)
                    if retry is not None:
                        if retry == 0:
                            raise
                        else:
                            retry -= 1
                    sleep(retry_wait)
                    continue
                except requests.exceptions.ConnectionError as e:
                    LOG.warning("%s: Connection error - %s", ID, e)
                    if retry is not None:
                        if retry == 0:
                            raise
                        else:
                            retry -= 1
                    sleep(retry_wait)
                    continue
        return f_retry
    return _req_retry


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
