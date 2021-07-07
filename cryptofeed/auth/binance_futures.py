'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import hashlib
import hmac
import time
import urllib.parse
import requests


def create_sign(key_secret, params):
    query_string = urllib.parse.urlencode(params)
    signature = hmac.new(key_secret.encode(), msg=query_string.encode(), digestmod=hashlib.sha256).hexdigest()
    return signature


def get_timestamp():
    return int(round(time.time() * 1000))


def get_listenKey(key_api, key_secret):
    params = {'recvWindow': 60000,
              'timestamp': get_timestamp()}
    signature = create_sign(key_secret, params)
    params['signature'] = signature
    headers = {'Content-Type': 'application/json',
               "X-MBX-APIKEY": key_api}
    r = requests.post("https://fapi.binance.com/fapi/v1/listenKey",
                      params=params,
                      headers=headers)
    return r.json()['listenKey']
