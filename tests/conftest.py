'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pathlib

import pytest

from cryptofeed.capture import corpus_filename
from cryptofeed.symbols import Symbols


TESTS_ROOT = pathlib.Path(__file__).parent
CORPUS_DIR = TESTS_ROOT.parent / 'sample_data'


LAYERS = ('unit', 'playback', 'backend', 'live', 'bench')


def pytest_collection_modifyitems(items):
    for item in items:
        try:
            layer = pathlib.Path(item.path).relative_to(TESTS_ROOT).parts[0]
        except (ValueError, IndexError):
            continue
        if layer in LAYERS:
            item.add_marker(getattr(pytest.mark, layer))


@pytest.fixture
def test_config() -> str:
    return str(TESTS_ROOT / 'config_test.yaml')


@pytest.fixture
def corpus_path():
    def _corpus_path(exchange: str) -> str:
        for compressed in (True, False):
            path = CORPUS_DIR / corpus_filename(exchange, compressed)
            if path.exists():
                return str(path)
        raise FileNotFoundError(f'no recording for {exchange} in {CORPUS_DIR} - record one with "make corpus EXCHANGE={exchange}"')
    return _corpus_path


@pytest.fixture
def clean_symbols():
    Symbols.clear()
    yield Symbols
    Symbols.clear()
