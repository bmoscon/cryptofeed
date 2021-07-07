'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import hashlib
import hmac
import random
import string
from yapic import json


def generate_auth(conn, key_id: str, key_secret: str) -> dict:
    # https://api.bequant.io/#socket-session-authentication

    # Nonce should be random string
    nonce = 'h'.join(random.choices(string.ascii_letters + string.digits, k=16)).encode('utf-8')

    signature = hmac.new(key_secret.encode('utf-8'), nonce, hashlib.sha256).hexdigest()

    login = {
        "method": "login",
        "params": {
            "algo": "HS256",
            "pKey": key_id,
            "nonce": nonce.decode(),
            "signature": signature
        },
        "id": conn.uuid
    }
    return json.dumps(login)
