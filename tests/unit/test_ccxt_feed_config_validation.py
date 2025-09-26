"""
Test CCXT Feed configuration validation integration.

Tests that CcxtFeed properly validates configuration using Pydantic models
and provides descriptive error messages per requirements.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
import sys

from cryptofeed.defines import TRADES, L2_BOOK


@pytest.fixture(autouse=True)
def clear_ccxt_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ccxt modules are absent unless explicitly injected."""
    for name in [
        "ccxt",
        "ccxt.async_support",
        "ccxt.async_support.backpack",
        "ccxt.pro",
        "ccxt.pro.backpack",
    ]:
        monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.fixture
def mock_ccxt(monkeypatch):
    """Mock ccxt for testing without external dependencies."""
    markets = {
        "BTC/USDT": {
            "id": "BTC_USDT",
            "symbol": "BTC/USDT",
            "base": "BTC",
            "quote": "USDT",
            "limits": {"amount": {"min": 0.0001}},
        }
    }

    class MockAsyncClient:
        def __init__(self):
            pass

        async def load_markets(self):
            return markets

        async def close(self):
            pass

    class MockProClient:
        def __init__(self):
            pass

    # Mock the dynamic imports
    mock_ccxt_data = {
        "async_client": MockAsyncClient,
        "pro_client": MockProClient,
        "markets": markets
    }

    def mock_dynamic_import(path: str):
        if path == "ccxt.async_support":
            return type('AsyncSupport', (), {'backpack': MockAsyncClient})
        elif path == "ccxt.pro":
            return type('Pro', (), {'backpack': MockProClient})
        else:
            raise ImportError(f"No module named '{path}'")

    monkeypatch.setattr(
        'cryptofeed.exchanges.ccxt_generic._dynamic_import',
        mock_dynamic_import
    )

    return mock_ccxt_data


class TestCcxtFeedConfigValidation:
    """Test that CcxtFeed validates configuration properly."""

    def test_valid_configuration_works(self, mock_ccxt):
        """Valid configurations should work without errors."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        # Test with legacy dict format
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES],
            proxies={"rest": "http://proxy:8080"},
            ccxt_options={"api_key": "key", "secret": "secret", "sandbox": True}
        )

        assert feed.ccxt_exchange_id == "backpack"
        assert feed.proxies["rest"] == "http://proxy:8080"
        assert feed.ccxt_options["apiKey"] == "key"
        assert feed.ccxt_options["sandbox"] is True

    def test_invalid_exchange_id_raises_descriptive_error(self, mock_ccxt):
        """Invalid exchange ID should raise descriptive error."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        with pytest.raises(ValueError, match="Invalid CCXT configuration for exchange ''"):
            CcxtFeed(
                exchange_id="",  # Invalid: empty string
                symbols=["BTC-USDT"],
                channels=[TRADES]
            )

        with pytest.raises(ValueError, match="Invalid CCXT configuration for exchange 'BINANCE'"):
            CcxtFeed(
                exchange_id="BINANCE",  # Invalid: uppercase
                symbols=["BTC-USDT"],
                channels=[TRADES]
            )

    def test_invalid_proxy_raises_descriptive_error(self, mock_ccxt):
        """Invalid proxy configuration should raise descriptive error."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        with pytest.raises(ValueError, match="Invalid CCXT configuration"):
            CcxtFeed(
                exchange_id="backpack",
                symbols=["BTC-USDT"],
                channels=[TRADES],
                proxies={"rest": "invalid-url"}  # Missing scheme
            )

    def test_invalid_ccxt_options_raise_descriptive_error(self, mock_ccxt):
        """Invalid CCXT options should raise descriptive errors."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        # API key without secret
        with pytest.raises(ValueError, match="Invalid CCXT configuration"):
            CcxtFeed(
                exchange_id="backpack",
                symbols=["BTC-USDT"],
                channels=[TRADES],
                ccxt_options={"api_key": "key"}  # Missing secret
            )

        # Invalid rate limit
        with pytest.raises(ValueError, match="Invalid CCXT configuration"):
            CcxtFeed(
                exchange_id="backpack",
                symbols=["BTC-USDT"],
                channels=[TRADES],
                ccxt_options={"rate_limit": 0}  # Below minimum
            )

    def test_typed_configuration_works(self, mock_ccxt):
        """Using typed Pydantic configuration should work."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        from cryptofeed.exchanges.ccxt_config import (
            CcxtExchangeConfig,
            CcxtProxyConfig,
            CcxtOptionsConfig
        )

        config = CcxtExchangeConfig(
            exchange_id="backpack",
            proxies=CcxtProxyConfig(rest="http://proxy:8080"),
            ccxt_options=CcxtOptionsConfig(
                api_key="key",
                secret="secret",
                sandbox=True,
                custom_option="custom_value"
            )
        )

        feed = CcxtFeed(
            config=config,
            symbols=["BTC-USDT"],
            channels=[TRADES]
        )

        assert feed.ccxt_exchange_id == "backpack"
        assert feed.proxies["rest"] == "http://proxy:8080"
        assert feed.ccxt_options["apiKey"] == "key"
        assert feed.ccxt_options["custom_option"] == "custom_value"

    def test_configuration_extension_hooks(self, mock_ccxt):
        """Exchange-specific options should be supported."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES],
            ccxt_options={
                "api_key": "key",
                "secret": "secret",
                # Exchange-specific options
                "backpack_specific_flag": True,
                "custom_endpoint": "wss://custom.backpack.exchange",
                "special_parameter": 42
            }
        )

        # Extension options should pass through to CCXT
        assert feed.ccxt_options["backpack_specific_flag"] is True
        assert feed.ccxt_options["custom_endpoint"] == "wss://custom.backpack.exchange"
        assert feed.ccxt_options["special_parameter"] == 42

    def test_transport_configuration_validation(self, mock_ccxt):
        """Transport configuration should be validated."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        # Valid transport config
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES],
            snapshot_interval=60,
            websocket_enabled=True,
            rest_only=False
        )

        assert feed.ccxt_config.transport.snapshot_interval == 60
        assert feed.ccxt_config.transport.websocket_enabled is True

        # Invalid: conflicting transport modes
        with pytest.raises(ValueError, match="Invalid CCXT configuration"):
            CcxtFeed(
                exchange_id="backpack",
                symbols=["BTC-USDT"],
                channels=[TRADES],
                rest_only=True,
                websocket_enabled=True  # Conflicting with rest_only
            )

    def test_backward_compatibility_maintained(self, mock_ccxt):
        """Existing code using dict configs should continue working."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed

        # This should work exactly as before, with added validation
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES],
            proxies={"rest": "socks5://proxy:1080"},
            ccxt_options={"rateLimit": 1000, "enableRateLimit": True}
        )

        # But now with proper type conversion
        assert feed.ccxt_options["rateLimit"] == 1000
        assert isinstance(feed.ccxt_config.proxies, object)  # Should be Pydantic model
        assert feed.ccxt_config.exchange_id == "backpack"