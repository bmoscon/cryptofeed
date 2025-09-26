"""
CCXT Configuration Models with Pydantic v2 validation.

Provides type-safe configuration for CCXT exchanges following
engineering principles from CLAUDE.md:
- SOLID: Single responsibility for configuration validation
- KISS: Simple, clear configuration models
- NO LEGACY: Modern Pydantic v2 only
- START SMALL: Core fields first, extensible for future needs
"""
from __future__ import annotations

from typing import Optional, Dict, Any, Union, Literal
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator


class CcxtProxyConfig(BaseModel):
    """Proxy configuration for CCXT transports."""
    model_config = ConfigDict(frozen=True, extra='forbid')

    rest: Optional[str] = Field(None, description="HTTP proxy URL for REST requests")
    websocket: Optional[str] = Field(None, description="WebSocket proxy URL for streams")

    @field_validator('rest', 'websocket')
    @classmethod
    def validate_proxy_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate proxy URL format."""
        if v is None:
            return v

        # Basic URL validation
        if '://' not in v:
            raise ValueError("Proxy URL must include scheme (e.g., socks5://host:port)")

        # Validate supported schemes
        supported_schemes = {'http', 'https', 'socks4', 'socks5'}
        scheme = v.split('://')[0].lower()
        if scheme not in supported_schemes:
            raise ValueError(f"Proxy scheme '{scheme}' not supported. Use: {supported_schemes}")

        return v


class CcxtOptionsConfig(BaseModel):
    """CCXT client options with validation."""
    model_config = ConfigDict(extra='allow')  # Allow extra fields for exchange-specific options

    # Core CCXT options with validation
    api_key: Optional[str] = Field(None, description="Exchange API key")
    secret: Optional[str] = Field(None, description="Exchange secret key")
    password: Optional[str] = Field(None, description="Exchange passphrase (if required)")
    sandbox: bool = Field(False, description="Use sandbox/testnet environment")
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Rate limit in ms")
    enable_rate_limit: bool = Field(True, description="Enable built-in rate limiting")
    timeout: Optional[int] = Field(None, ge=1000, le=120000, description="Request timeout in ms")

    # Exchange-specific extensions allowed via extra='allow'

    @field_validator('api_key', 'secret', 'password')
    @classmethod
    def validate_credentials(cls, v: Optional[str]) -> Optional[str]:
        """Validate credential format."""
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError("Credentials must be strings")
        if len(v.strip()) == 0:
            raise ValueError("Credentials cannot be empty strings")
        return v.strip()


class CcxtTransportConfig(BaseModel):
    """Transport-level configuration for REST and WebSocket."""
    model_config = ConfigDict(frozen=True, extra='forbid')

    snapshot_interval: int = Field(30, ge=1, le=3600, description="L2 snapshot interval in seconds")
    websocket_enabled: bool = Field(True, description="Enable WebSocket streams")
    rest_only: bool = Field(False, description="Force REST-only mode")
    use_market_id: bool = Field(False, description="Use market ID instead of symbol for requests")

    @model_validator(mode='after')
    def validate_transport_modes(self) -> 'CcxtTransportConfig':
        """Ensure transport configuration is consistent."""
        if self.rest_only and self.websocket_enabled:
            raise ValueError("Cannot enable WebSocket when rest_only=True")
        return self


class CcxtExchangeConfig(BaseModel):
    """Complete CCXT exchange configuration with validation."""
    model_config = ConfigDict(frozen=True, extra='forbid')

    # Core CCXT configuration
    exchange_id: str = Field(..., description="CCXT exchange identifier (e.g., 'backpack')")
    proxies: Optional[CcxtProxyConfig] = Field(None, description="Proxy configuration")
    ccxt_options: Optional[CcxtOptionsConfig] = Field(None, description="CCXT client options")
    transport: Optional[CcxtTransportConfig] = Field(None, description="Transport configuration")

    @field_validator('exchange_id')
    @classmethod
    def validate_exchange_id(cls, v: str) -> str:
        """Validate exchange ID format."""
        if not v or not isinstance(v, str):
            raise ValueError("Exchange ID must be a non-empty string")

        # Basic format validation - should be lowercase identifier
        if not v.islower() or not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Exchange ID must be lowercase alphanumeric with optional underscores/hyphens")

        return v.strip()

    @model_validator(mode='after')
    def validate_configuration_consistency(self) -> 'CcxtExchangeConfig':
        """Validate overall configuration consistency."""
        # If API credentials provided, ensure they're complete
        if self.ccxt_options and self.ccxt_options.api_key:
            if not self.ccxt_options.secret:
                raise ValueError("API secret required when API key is provided")

        return self

    def to_ccxt_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by CCXT clients."""
        result = {}

        if self.ccxt_options:
            # Convert Pydantic model to dict, excluding None values
            ccxt_dict = self.ccxt_options.model_dump(exclude_none=True)

            # Map to CCXT-expected field names
            field_mapping = {
                'api_key': 'apiKey',
                'secret': 'secret',
                'password': 'password',
                'sandbox': 'sandbox',
                'rate_limit': 'rateLimit',
                'enable_rate_limit': 'enableRateLimit',
                'timeout': 'timeout'
            }

            for pydantic_field, ccxt_field in field_mapping.items():
                if pydantic_field in ccxt_dict:
                    result[ccxt_field] = ccxt_dict[pydantic_field]

            # Add any extra fields directly (exchange-specific options)
            for field, value in ccxt_dict.items():
                if field not in field_mapping:
                    result[field] = value

        return result


# Convenience function for backward compatibility
def validate_ccxt_config(
    exchange_id: str,
    proxies: Optional[Dict[str, str]] = None,
    ccxt_options: Optional[Dict[str, Any]] = None,
    **kwargs
) -> CcxtExchangeConfig:
    """
    Validate and convert legacy dict-based config to typed Pydantic model.

    Provides backward compatibility while adding validation.
    """
    # Convert dict-based configs to Pydantic models
    proxy_config = None
    if proxies:
        proxy_config = CcxtProxyConfig(**proxies)

    options_config = None
    if ccxt_options:
        options_config = CcxtOptionsConfig(**ccxt_options)

    # Handle transport options from kwargs
    transport_fields = {'snapshot_interval', 'websocket_enabled', 'rest_only', 'use_market_id'}
    transport_kwargs = {k: v for k, v in kwargs.items() if k in transport_fields}
    transport_config = CcxtTransportConfig(**transport_kwargs) if transport_kwargs else None

    return CcxtExchangeConfig(
        exchange_id=exchange_id,
        proxies=proxy_config,
        ccxt_options=options_config,
        transport=transport_config
    )


__all__ = [
    'CcxtProxyConfig',
    'CcxtOptionsConfig',
    'CcxtTransportConfig',
    'CcxtExchangeConfig',
    'validate_ccxt_config'
]