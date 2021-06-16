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

    # Now required to pass timestamp with string to sign. Timestamp should exactly match header timestamp
    now = str(int(time.time() * 1000))
    str_to_sign = now + str_to_sign
    signature = base64.b64encode(hmac.new(key_secret.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest())
    # Passphrase must now be encrypted by key_secret
    passphrase = base64.b64encode(hmac.new(key_secret.encode('utf-8'), key_passphrase.encode('utf-8'), hashlib.sha256).digest())

    # API key version is currently 2 (whereas API version is anywhere from 1-3 ¯\_(ツ)_/¯)
    header = {
        "KC-API-KEY": key_id,
        "KC-API-SIGN": signature.decode(),
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": passphrase.decode(),
        "KC-API-KEY-VERSION": "2"
    }
    return header
