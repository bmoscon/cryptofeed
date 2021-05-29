'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
import hashlib
import hmac
import json
import time


def generate_token(key_id: str, key_secret: str, request: str, account_name=None, payload=None) -> dict:
    if not payload:
        payload = {}
    payload['request'] = request
    payload['nonce'] = int(time.time() * 1000)

    if account_name:
        payload['account'] = account_name

    b64_payload = base64.b64encode(json.dumps(payload).encode('utf-8'))
    signature = hmac.new(key_secret.encode('utf-8'), b64_payload, hashlib.sha384).hexdigest()

    return {
        'X-GEMINI-PAYLOAD': b64_payload.decode(),
        'X-GEMINI-APIKEY': key_id,
        'X-GEMINI-SIGNATURE': signature
    }
