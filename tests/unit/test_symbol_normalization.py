'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest

from cryptofeed.capture import Replayer
from cryptofeed.exchanges import EXCHANGE_MAP
from tests.util import CONFIG, capture_path, feed_entry


@pytest.mark.playback
@pytest.mark.parametrize('exchange', sorted(EXCHANGE_MAP))
async def test_symbol_conversion(exchange):
    replayer = Replayer(capture_path(exchange))
    feed = replayer.build_feed(config=CONFIG)
    replayer.prepare(feed)
    try:
        await feed.load_symbols(conn=feed.http_conn)
        symbols = feed.symbol_mapping()
        assert symbols

        for normalized, original in symbols.items():
            assert feed.std_symbol_to_exchange_symbol(normalized) == original
            assert feed.exchange_symbol_to_std_symbol(original) == normalized

        entry = feed_entry(exchange)
        assert set(entry['symbols']) <= set(symbols)
        assert symbols == entry['symbols_snapshot']['normalized']
    finally:
        await feed.http_conn.close()
