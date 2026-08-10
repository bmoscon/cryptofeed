'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal


try:
    from msgspec import json as _msgspec_json

    BACKEND = 'msgspec'
    _decoder = _msgspec_json.Decoder()
    _decimal_decoder = _msgspec_json.Decoder(float_hook=Decimal)
    # decimal_format='number' - msgspec defaults to encoding Decimal as a JSON string
    _encoder = _msgspec_json.Encoder(decimal_format='number')

    def loads(data, parse_float=None):
        if parse_float is None:
            return _decoder.decode(data)
        if parse_float is Decimal:
            return _decimal_decoder.decode(data)
        return _msgspec_json.Decoder(float_hook=parse_float).decode(data)

    def dumps(obj) -> str:
        return _encoder.encode(obj).decode()

    def dumpb(obj) -> bytes:
        return _encoder.encode(obj)

except ImportError:
    # fallback
    import json as _stdlib_json

    BACKEND = 'json'

    def loads(data, parse_float=None):
        return _stdlib_json.loads(data, parse_float=parse_float)

    def dumps(obj) -> str:
        return _stdlib_json.dumps(obj, separators=(',', ':'), default=str)

    def dumpb(obj) -> bytes:
        return dumps(obj).encode()
