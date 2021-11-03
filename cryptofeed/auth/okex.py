'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
import hmac
import requests


def get_server_time():
    url = "https://www.okex.com/api/v5/public/time"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['data'][0]['ts']
    else:
        return ""


def server_timestamp():
    server_time = get_server_time()
    return int(server_time) / 1000


def create_sign(timestamp: str, key_secret: str):
    message = timestamp + 'GET' + '/users/self/verify'
    mac = hmac.new(bytes(key_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)
    return sign


def generate_token(key_id: str, key_secret: str) -> dict:
    timestamp = str(server_timestamp())
    sign = create_sign(timestamp, key_secret)
    return timestamp, sign
