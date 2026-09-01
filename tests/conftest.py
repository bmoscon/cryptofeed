import pytest

from cryptofeed.symbols import Symbols


@pytest.fixture(autouse=True)
def clear_symbols():
    Symbols.clear()
    yield
    Symbols.clear()
