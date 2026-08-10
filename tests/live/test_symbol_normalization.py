'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.exchanges import EXCHANGE_MAP


@pytest.mark.parametrize("exchange", list(EXCHANGE_MAP.keys()))
def test_symbol_conversion(exchange):
    feed = EXCHANGE_MAP[exchange]()
    symbols = feed.symbol_mapping()
    for normalized, original in symbols.items():
        assert feed.std_symbol_to_exchange_symbol(normalized) == original
        assert feed.exchange_symbol_to_std_symbol(original) == normalized
