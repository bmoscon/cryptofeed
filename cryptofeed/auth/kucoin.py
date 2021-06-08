'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import time
import hmac
import base64
import hashlib


def generate_token(key_id: str, key_secret: str, key_passphrase: str, str_to_sign: str) -> dict:
    # https://docs.kucoin.com/#authentication

    now = int(time.time() * 1000)
    str_to_sign = str(now) + str_to_sign
    signature = base64.b64encode(
        hmac.new(key_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())

    header = {
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": str(now),
        "KC-API-KEY": key_id,
        "KC-API-PASSPHRASE": key_passphrase,
        "KC-API-KEY-VERSION": "3"
    }
    return header
