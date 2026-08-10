'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import glob
import json as stdlib_json
from decimal import Decimal
from pathlib import Path

import pytest

from cryptofeed import _json
from cryptofeed.capture import CaptureReader, payload_of


CORPUS = Path(__file__).parents[2] / 'sample_data'
VENUES = ('BINANCE', 'KRAKEN', 'COINBASE', 'BITFINEX', 'BITSTAMP')
MAX_PAYLOADS = 4000


def load_payloads():
    payloads = []
    for venue in VENUES:
        matches = glob.glob(str(CORPUS / f'{venue}.jsonl*'))
        if not matches:
            continue
        for record in CaptureReader(matches[0]).records():
            if record['t'] != 'recv' or 'data' not in record:
                continue
            payload = payload_of(record)
            if not isinstance(payload, str) or not payload.strip().startswith(('{', '[')):
                continue
            payloads.append(payload)
            if len(payloads) >= MAX_PAYLOADS:
                return payloads
    return payloads


@pytest.fixture(scope='module')
def payloads():
    data = load_payloads()
    if not data:
        pytest.skip('no corpus payloads available')
    return data


def test_decode_decimal(benchmark, payloads):
    benchmark(lambda: [_json.loads(p, parse_float=Decimal) for p in payloads])


def test_decode_float(benchmark, payloads):
    benchmark(lambda: [_json.loads(p) for p in payloads])


def test_decode_decimal_stdlib(benchmark, payloads):
    benchmark(lambda: [stdlib_json.loads(p, parse_float=Decimal) for p in payloads])


def test_encode(benchmark, payloads):
    objects = [stdlib_json.loads(p) for p in payloads]
    benchmark(lambda: [_json.dumps(o) for o in objects])


def test_encode_bytes(benchmark, payloads):
    objects = [stdlib_json.loads(p) for p in payloads]
    benchmark(lambda: [_json.dumpb(o) for o in objects])


def test_decode_is_exact(payloads):
    high_precision = '{"price": "0.30000000000000004", "size": 1.000000000000000009}'
    decoded = _json.loads(high_precision, parse_float=Decimal)
    assert decoded['size'] == Decimal('1.000000000000000009'), 'the codec is rounding through float'
