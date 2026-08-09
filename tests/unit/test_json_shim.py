'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import builtins
import importlib
import json as stdlib_json
from datetime import datetime as dt, timezone
from decimal import Decimal

import pytest

from cryptofeed import _json


PAYLOADS = [
    '{"price": 0.30000000000000004, "size": 1.5, "id": 12345}',
    '{"price": 123456789.123456789012345678901234567890}',
    '{"bids": [["0.1", "2.5"], ["0.09", "3"]], "ts": 1618677810244}',
    '{"connectionID": 18239578009413566319}',
    '{"nested": {"a": [1, 2.5, "x", null, true]}}',
]


def test_loads_default_floats():
    out = _json.loads('{"p": 0.1, "n": 7}')
    assert type(out['p']) is float
    assert type(out['n']) is int


def test_loads_decimal_exact():
    out = _json.loads('{"p": 0.30000000000000004}', parse_float=Decimal)
    assert out['p'] == Decimal('0.30000000000000004')
    out = _json.loads('{"p": 123456789.123456789012345678901234567890}', parse_float=Decimal)
    assert out['p'] == Decimal('123456789.123456789012345678901234567890')


def test_loads_decimal_only_affects_floats():
    out = _json.loads('{"i": 12345, "f": 1.5}', parse_float=Decimal)
    assert type(out['i']) is int
    assert out['f'] == Decimal('1.5')


def test_loads_wide_int():
    assert _json.loads('{"id": 18239578009413566319}')['id'] == 18239578009413566319


def test_loads_bytes_input():
    assert _json.loads(b'{"a": 1}') == {'a': 1}


def test_loads_error_is_valueerror():
    with pytest.raises(ValueError):
        _json.loads('')


def test_dumps_returns_str():
    out = _json.dumps({'a': 1})
    assert isinstance(out, str)
    assert stdlib_json.loads(out) == {'a': 1}


def test_dumps_decimal_as_number():
    # wire-format parity: Decimal must serialize as a bare JSON number
    assert _json.dumps({'p': Decimal('0.1')}) == '{"p":0.1}'
    assert _json.dumps(Decimal('123456789.123456789012345678901234567890')) == '123456789.123456789012345678901234567890'


def test_dumps_wide_int():
    assert _json.dumps({'id': 18239578009413566319}) == '{"id":18239578009413566319}'


def test_dumps_datetime():
    out = _json.dumps({'t': dt(2021, 4, 17, 16, 43, 30, 244075, tzinfo=timezone.utc)})
    assert out == '{"t":"2021-04-17T16:43:30.244075Z"}'


def test_roundtrip_identity_vs_stdlib():
    for p in PAYLOADS:
        assert _json.loads(p, parse_float=Decimal) == stdlib_json.loads(p, parse_float=Decimal)
        assert stdlib_json.loads(_json.dumps(stdlib_json.loads(p))) == stdlib_json.loads(p)


def test_stdlib_fallback_decode_identical(monkeypatch):
    real_import = builtins.__import__

    def no_msgspec(name, *args, **kwargs):
        if name == 'msgspec' or name.startswith('msgspec.'):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', no_msgspec)
    fallback = importlib.reload(_json)
    try:
        assert fallback.BACKEND == 'json'
        for p in PAYLOADS:
            assert fallback.loads(p, parse_float=Decimal) == stdlib_json.loads(p, parse_float=Decimal)
        assert isinstance(fallback.dumps({'a': 1}), str)
    finally:
        monkeypatch.undo()
        importlib.reload(_json)
        assert _json.BACKEND == 'msgspec'


def test_timestamp_normalize_accepts_iso_strings():
    from cryptofeed.exchange import Exchange
    expected = dt(2021, 4, 17, 16, 43, 30, 244075, tzinfo=timezone.utc).timestamp()
    assert Exchange.timestamp_normalize('2021-04-17T16:43:30.244075Z') == expected
    assert Exchange.timestamp_normalize(dt(2021, 4, 17, 16, 43, 30, 244075, tzinfo=timezone.utc)) == expected
    assert Exchange.timestamp_normalize('2021-04-17T18:43:30.244075+02:00') == expected


def test_date_format_accepts_iso_strings():
    from cryptofeed.symbols import Symbol
    assert Symbol.date_format('2021-11-30T12:00:00Z') == '21X30'
    assert Symbol.date_format('2021-09-24T12:00:00.000Z') == '21U24'
    assert Symbol.date_format(dt(2021, 11, 30, tzinfo=timezone.utc)) == '21X30'
    # pre-existing short formats unaffected
    assert Symbol.date_format('211130') == '21X30'


def test_bybit_timestamp_normalize_str():
    from cryptofeed.exchanges.bybit import Bybit
    assert Bybit.timestamp_normalize(1618677810244) == 1618677810.244
    iso = '2021-04-17T16:43:30.244075+00:00'
    assert Bybit.timestamp_normalize(iso) == dt.fromisoformat(iso).timestamp()


def test_bithumb_timestamp_normalize_str():
    from cryptofeed.exchanges.bithumb import Bithumb
    from datetime import timedelta
    naive = dt(2021, 6, 2, 8, 43, 34, 555058)
    assert Bithumb.timestamp_normalize('2021-06-02 08:43:34.555058') == (naive - timedelta(hours=9)).timestamp()
