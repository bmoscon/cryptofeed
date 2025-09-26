"""
Tests for CCXT Pydantic configuration validation.

Tests follow TDD principles from CLAUDE.md:
- Write tests first based on expected behavior
- No mocks for configuration validation
- Test validation errors thoroughly
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from cryptofeed.exchanges.ccxt_config import (
    CcxtProxyConfig,
    CcxtOptionsConfig,
    CcxtTransportConfig,
    CcxtExchangeConfig,
    validate_ccxt_config
)


class TestCcxtProxyConfig:
    """Test proxy configuration validation."""

    def test_valid_proxy_config(self):
        """Valid proxy configurations should pass validation."""
        config = CcxtProxyConfig(
            rest="http://proxy:8080",
            websocket="socks5://user:pass@proxy:1080"
        )

        assert config.rest == "http://proxy:8080"
        assert config.websocket == "socks5://user:pass@proxy:1080"

    def test_optional_proxy_fields(self):
        """Proxy fields should be optional."""
        config = CcxtProxyConfig()

        assert config.rest is None
        assert config.websocket is None

        config2 = CcxtProxyConfig(rest="http://proxy:8080")
        assert config2.rest == "http://proxy:8080"
        assert config2.websocket is None

    def test_invalid_proxy_url_no_scheme(self):
        """Proxy URLs without scheme should be rejected."""
        with pytest.raises(ValidationError, match="must include scheme"):
            CcxtProxyConfig(rest="proxy:8080")

    def test_invalid_proxy_scheme(self):
        """Unsupported proxy schemes should be rejected."""
        with pytest.raises(ValidationError, match="not supported"):
            CcxtProxyConfig(rest="ftp://proxy:8080")

    def test_proxy_config_immutable(self):
        """Proxy config should be immutable (frozen)."""
        config = CcxtProxyConfig(rest="http://proxy:8080")

        with pytest.raises(ValidationError):
            config.rest = "http://other:8080"


class TestCcxtOptionsConfig:
    """Test CCXT options configuration validation."""

    def test_valid_options_config(self):
        """Valid options configuration should pass."""
        config = CcxtOptionsConfig(
            api_key="test_key",
            secret="test_secret",
            sandbox=True,
            rate_limit=1000,
            enable_rate_limit=True,
            timeout=30000
        )

        assert config.api_key == "test_key"
        assert config.secret == "test_secret"
        assert config.sandbox is True
        assert config.rate_limit == 1000
        assert config.timeout == 30000

    def test_options_allow_extra_fields(self):
        """Options should allow exchange-specific extra fields."""
        config = CcxtOptionsConfig(
            api_key="key",
            secret="secret",
            # Exchange-specific fields
            custom_option="value",
            special_flag=True
        )

        assert config.api_key == "key"
        # Extra fields should be accessible via model_dump()
        dump = config.model_dump()
        assert dump["custom_option"] == "value"
        assert dump["special_flag"] is True

    def test_rate_limit_validation(self):
        """Rate limit should be within valid range."""
        # Valid range
        config = CcxtOptionsConfig(rate_limit=1000)
        assert config.rate_limit == 1000

        # Too low
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            CcxtOptionsConfig(rate_limit=0)

        # Too high
        with pytest.raises(ValidationError, match="less than or equal to 10000"):
            CcxtOptionsConfig(rate_limit=20000)

    def test_timeout_validation(self):
        """Timeout should be within valid range."""
        # Valid range
        config = CcxtOptionsConfig(timeout=30000)
        assert config.timeout == 30000

        # Too low
        with pytest.raises(ValidationError, match="greater than or equal to 1000"):
            CcxtOptionsConfig(timeout=500)

        # Too high
        with pytest.raises(ValidationError, match="less than or equal to 120000"):
            CcxtOptionsConfig(timeout=150000)

    def test_credentials_validation(self):
        """Credentials should be validated."""
        # Valid credentials
        config = CcxtOptionsConfig(api_key="key", secret="secret")
        assert config.api_key == "key"
        assert config.secret == "secret"

        # Empty strings should be rejected
        with pytest.raises(ValidationError, match="cannot be empty"):
            CcxtOptionsConfig(api_key="")

        with pytest.raises(ValidationError, match="cannot be empty"):
            CcxtOptionsConfig(secret="   ")  # Whitespace only


class TestCcxtTransportConfig:
    """Test transport configuration validation."""

    def test_valid_transport_config(self):
        """Valid transport configuration should pass."""
        config = CcxtTransportConfig(
            snapshot_interval=60,
            websocket_enabled=True,
            rest_only=False,
            use_market_id=False
        )

        assert config.snapshot_interval == 60
        assert config.websocket_enabled is True
        assert config.rest_only is False

    def test_transport_defaults(self):
        """Transport should have sensible defaults."""
        config = CcxtTransportConfig()

        assert config.snapshot_interval == 30
        assert config.websocket_enabled is True
        assert config.rest_only is False
        assert config.use_market_id is False

    def test_snapshot_interval_validation(self):
        """Snapshot interval should be within valid range."""
        # Valid range
        config = CcxtTransportConfig(snapshot_interval=300)
        assert config.snapshot_interval == 300

        # Too low
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            CcxtTransportConfig(snapshot_interval=0)

        # Too high
        with pytest.raises(ValidationError, match="less than or equal to 3600"):
            CcxtTransportConfig(snapshot_interval=7200)

    def test_transport_mode_validation(self):
        """Transport modes should be consistent."""
        # Valid: rest_only=True, websocket_enabled=False (implied)
        config1 = CcxtTransportConfig(rest_only=True, websocket_enabled=False)
        assert config1.rest_only is True
        assert config1.websocket_enabled is False

        # Invalid: conflicting settings
        with pytest.raises(ValidationError, match="Cannot enable WebSocket when rest_only=True"):
            CcxtTransportConfig(rest_only=True, websocket_enabled=True)


class TestCcxtExchangeConfig:
    """Test complete exchange configuration validation."""

    def test_valid_exchange_config(self):
        """Complete valid configuration should pass."""
        config = CcxtExchangeConfig(
            exchange_id="backpack",
            proxies=CcxtProxyConfig(rest="http://proxy:8080"),
            ccxt_options=CcxtOptionsConfig(api_key="key", secret="secret"),
            transport=CcxtTransportConfig(snapshot_interval=60)
        )

        assert config.exchange_id == "backpack"
        assert config.proxies.rest == "http://proxy:8080"
        assert config.ccxt_options.api_key == "key"
        assert config.transport.snapshot_interval == 60

    def test_minimal_exchange_config(self):
        """Minimal configuration should work."""
        config = CcxtExchangeConfig(exchange_id="binance")

        assert config.exchange_id == "binance"
        assert config.proxies is None
        assert config.ccxt_options is None
        assert config.transport is None

    def test_exchange_id_validation(self):
        """Exchange ID should be validated."""
        # Valid IDs
        for exchange_id in ["backpack", "binance", "coinbase_pro", "huobi-global"]:
            config = CcxtExchangeConfig(exchange_id=exchange_id)
            assert config.exchange_id == exchange_id

        # Invalid IDs
        with pytest.raises(ValidationError, match="must be a non-empty string"):
            CcxtExchangeConfig(exchange_id="")

        with pytest.raises(ValidationError, match="must be lowercase"):
            CcxtExchangeConfig(exchange_id="Binance")

        with pytest.raises(ValidationError, match="must be lowercase"):
            CcxtExchangeConfig(exchange_id="binance@pro")

    def test_configuration_consistency_validation(self):
        """Configuration should be internally consistent."""
        # Valid: API key with secret
        config = CcxtExchangeConfig(
            exchange_id="backpack",
            ccxt_options=CcxtOptionsConfig(api_key="key", secret="secret")
        )
        assert config.ccxt_options.api_key == "key"

        # Invalid: API key without secret
        with pytest.raises(ValidationError, match="API secret required when API key is provided"):
            CcxtExchangeConfig(
                exchange_id="backpack",
                ccxt_options=CcxtOptionsConfig(api_key="key")  # No secret
            )

    def test_to_ccxt_dict_conversion(self):
        """Configuration should convert to CCXT-compatible dict."""
        config = CcxtExchangeConfig(
            exchange_id="backpack",
            ccxt_options=CcxtOptionsConfig(
                api_key="test_key",
                secret="test_secret",
                sandbox=True,
                rate_limit=1000,
                enable_rate_limit=True,
                custom_field="custom_value"  # Exchange-specific option
            )
        )

        ccxt_dict = config.to_ccxt_dict()

        # Standard fields should be mapped to CCXT names
        assert ccxt_dict["apiKey"] == "test_key"
        assert ccxt_dict["secret"] == "test_secret"
        assert ccxt_dict["sandbox"] is True
        assert ccxt_dict["rateLimit"] == 1000
        assert ccxt_dict["enableRateLimit"] is True

        # Custom fields should pass through
        assert ccxt_dict["custom_field"] == "custom_value"

    def test_to_ccxt_dict_excludes_none(self):
        """CCXT dict should exclude None values."""
        config = CcxtExchangeConfig(
            exchange_id="backpack",
            ccxt_options=CcxtOptionsConfig(api_key="key", secret="secret")  # timeout is None
        )

        ccxt_dict = config.to_ccxt_dict()

        assert "timeout" not in ccxt_dict
        assert ccxt_dict["apiKey"] == "key"


class TestValidateCcxtConfig:
    """Test backward compatibility validation function."""

    def test_validate_legacy_dict_config(self):
        """Legacy dict-based configuration should be validated."""
        config = validate_ccxt_config(
            exchange_id="backpack",
            proxies={"rest": "http://proxy:8080", "websocket": "socks5://proxy:1080"},
            ccxt_options={"api_key": "key", "secret": "secret", "sandbox": True},
            snapshot_interval=60,
            websocket_enabled=True
        )

        assert isinstance(config, CcxtExchangeConfig)
        assert config.exchange_id == "backpack"
        assert config.proxies.rest == "http://proxy:8080"
        assert config.ccxt_options.api_key == "key"
        assert config.transport.snapshot_interval == 60

    def test_validate_minimal_config(self):
        """Minimal configuration should validate."""
        config = validate_ccxt_config(exchange_id="binance")

        assert config.exchange_id == "binance"
        assert config.proxies is None
        assert config.ccxt_options is None

    def test_validate_invalid_config_raises_error(self):
        """Invalid configuration should raise descriptive errors."""
        # Invalid exchange ID
        with pytest.raises(ValidationError):
            validate_ccxt_config(exchange_id="")

        # Invalid proxy
        with pytest.raises(ValidationError):
            validate_ccxt_config(
                exchange_id="backpack",
                proxies={"rest": "invalid-url"}
            )

        # Invalid CCXT options
        with pytest.raises(ValidationError):
            validate_ccxt_config(
                exchange_id="backpack",
                ccxt_options={"rate_limit": 0}  # Below minimum
            )