'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.defines import EXX
from cryptofeed.feedhandler import _EXCHANGES


@pytest.mark.parametrize("exchange", [e for e in _EXCHANGES.keys() if e not in [EXX]])
def test_symbol_conversion(exchange):
    feed = _EXCHANGES[exchange]()
    symbols = feed.symbol_mapping()
    for normalized, original in symbols.items():
        assert feed.std_symbol_to_exchange_symbol(normalized) == original
        assert feed.exchange_symbol_to_std_symbol(original) == normalized
