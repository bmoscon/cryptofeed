import pytest
from cryptofeed.types import COMPILED_WITH_ASSERTIONS, Ticker


@pytest.mark.skipif(not COMPILED_WITH_ASSERTIONS, reason="cython assertions not enabled")
def test_ticker_raises_with_bad_args_if_assertions_enabled():
    with pytest.raises(AssertionError):
        # bid and ask should be Decimal, not str
        Ticker(exchange="", symbol="", bid="1.0", ask="2.0", timestamp=None)
        
@pytest.mark.skipif(COMPILED_WITH_ASSERTIONS, reason="cython assertions enabled")
def test_ticker_does_not_raise_with_bad_args_if_assertions_not_enabled():
    # bid and ask should be Decimal, not str, but it should not raise
    Ticker(exchange="", symbol="", bid="1.0", ask="2.0", timestamp=None)