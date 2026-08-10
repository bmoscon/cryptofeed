'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import pathlib

import pytest

from cryptofeed.capture import CaptureReader, playback
from cryptofeed.exchanges import EXCHANGE_MAP

from .invariants import PlaybackValidator


EXPECTED = json.loads((pathlib.Path(__file__).parent / 'expected_counts.json').read_text())


def test_every_exchange_has_a_recording(corpus_path):
    missing = []
    for exchange in sorted(EXCHANGE_MAP):
        try:
            corpus_path(exchange)
        except FileNotFoundError:
            missing.append(exchange)
    assert not missing, f'exchanges with no recording: {missing}'


def test_expected_counts_cover_every_exchange():
    missing = sorted(set(EXCHANGE_MAP) - set(EXPECTED))
    stale = sorted(set(EXPECTED) - set(EXCHANGE_MAP))
    assert not missing, f'exchanges with no expected counts: {missing}'
    assert not stale, f'expected counts for exchanges that no longer exist: {stale}'


@pytest.mark.parametrize("exchange", sorted(EXCHANGE_MAP.keys()))
def test_exchange_playback(exchange, corpus_path, test_config, clean_symbols):
    path = corpus_path(exchange)
    reader = CaptureReader(path)
    validator = PlaybackValidator(exchange, candle_interval=reader.candle_interval)

    results = playback(path, callbacks=validator.callbacks(reader.config), config=test_config,
                       checksum_validation=True, cross_check=True)

    # every recorded frame reached a handler
    assert results['messages_processed'] == reader.count('recv')
    assert EXPECTED[exchange] == results['callbacks']
    assert not validator.violations, validator.violations.report()
