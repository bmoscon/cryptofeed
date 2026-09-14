'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os

from cryptofeed.exchanges import EXCHANGE_MAP
from tests.util import capture_path, expected_callbacks, read_metadata, replay

import pytest


def expected_message_count(exchange: str) -> int:
    count = 0
    for stream in read_metadata(exchange)['streams']:
        if stream['kind'] == 'ws':
            count += stream['messages']
        elif stream['address'] is not None:
            count += stream['requests']
    return count


@pytest.mark.playback
def test_no_missing_sample_data():
    expected = expected_callbacks()
    for exchange in EXCHANGE_MAP:
        assert os.path.exists(capture_path(exchange)), f'{exchange} - missing captures in {os.path.dirname(capture_path(exchange))}'
        metadata = read_metadata(exchange)
        assert metadata['version'] == 1
        assert [entry['exchange'] for entry in metadata['feeds']] == [exchange]
        assert exchange in expected
    assert set(expected) == set(EXCHANGE_MAP)


@pytest.mark.playback
@pytest.mark.parametrize('exchange', sorted(EXCHANGE_MAP))
def test_exchange_playback(exchange):
    results = replay(exchange)

    assert results.messages_processed == expected_message_count(exchange)
    assert results.callbacks == expected_callbacks()[exchange]
