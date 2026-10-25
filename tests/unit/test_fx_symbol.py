'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import FX
from cryptofeed.symbols import Symbol, str_to_symbol


def test_fx_symbol_round_trips_with_its_type():
    symbol = Symbol('EUR', 'USD', type=FX)

    parsed = str_to_symbol(symbol.normalized)

    assert parsed.type == FX
    assert parsed.normalized == symbol.normalized
