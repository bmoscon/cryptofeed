"""CCXT configuration models and validation helpers.

Functional-first refactor guidance:
- Keep configuration surfaces simple (FRs over NFRs).
- Use conventional commits such as ``feat(ccxt): tighten config validation`` when
  changing configuration behaviour.
- Advanced telemetry/performance tweaks belong in follow-up work.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cryptofeed.proxy import ProxySettings

from .extensions import CcxtConfigExtensions

if TYPE_CHECKING:  # pragma: no cover
    from .context import CcxtExchangeContext


class CcxtProxyConfig(BaseModel):
    """Proxy configuration for CCXT transports."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    rest: Optional[str] = Field(None, description="HTTP proxy URL for REST requests")
    websocket: Optional[str] = Field(None, description="WebSocket proxy URL for streams")

    @field_validator('rest', 'websocket')
    @classmethod
    def validate_proxy_url(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if '://' not in value:
            raise ValueError("Proxy URL must include scheme (e.g., socks5://host:port)")
        scheme = value.split('://', 1)[0].lower()
        if scheme not in {'http', 'https', 'socks4', 'socks5'}:
            raise ValueError(f"Proxy scheme '{scheme}' not supported. Use http/https/socks4/socks5")
        return value


class CcxtOptionsConfig(BaseModel):
    """CCXT client options with validation."""

    model_config = ConfigDict(extra='allow')

    api_key: Optional[str] = Field(None, description="Exchange API key")
    secret: Optional[str] = Field(None, description="Exchange secret key")
    password: Optional[str] = Field(None, description="Exchange passphrase (if required)")
    sandbox: bool = Field(False, description="Use sandbox/testnet environment")
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Rate limit in ms")
    enable_rate_limit: bool = Field(True, description="Enable built-in rate limiting")
    timeout: Optional[int] = Field(None, ge=1000, le=120000, description="Request timeout in ms")

    @field_validator('api_key', 'secret', 'password')
    @classmethod
    def validate_credentials(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not isinstance(value, str):
            raise ValueError("Credentials must be strings")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Credentials cannot be empty strings")
        return stripped


class CcxtTransportConfig(BaseModel):
    """Transport-level configuration for REST and WebSocket."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    snapshot_interval: int = Field(30, ge=1, le=3600, description="L2 snapshot interval in seconds")
    websocket_enabled: bool = Field(True, description="Enable WebSocket streams")
    rest_only: bool = Field(False, description="Force REST-only mode")
    use_market_id: bool = Field(False, description="Use market ID instead of symbol for requests")

    @model_validator(mode='after')
    def validate_transport_modes(self) -> 'CcxtTransportConfig':
        if self.rest_only and self.websocket_enabled:
            raise ValueError("Cannot enable WebSocket when rest_only=True")
        return self


def _validate_exchange_id(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("Exchange ID must be a non-empty string")
    normalized = value.strip()
    if not normalized.islower() or not normalized.replace('_', '').replace('-', '').isalnum():
        raise ValueError("Exchange ID must be lowercase alphanumeric with optional underscores/hyphens")
    return normalized


class CcxtConfig(BaseModel):
    """Top-level CCXT configuration model with extension hooks."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    exchange_id: str = Field(..., description="CCXT exchange identifier")
    api_key: Optional[str] = Field(None, description="Exchange API key")
    secret: Optional[str] = Field(None, description="Exchange secret key")
    passphrase: Optional[str] = Field(None, description="Exchange passphrase/password")
    sandbox: bool = Field(False, description="Enable CCXT sandbox/testnet")
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Rate limit in ms")
    timeout: Optional[int] = Field(None, ge=1000, le=120000, description="Request timeout in ms")
    enable_rate_limit: bool = Field(True, description="Enable CCXT built-in rate limiting")
    proxies: Optional[CcxtProxyConfig] = Field(None, description="Explicit proxy configuration")
    transport: Optional[CcxtTransportConfig] = Field(None, description="Transport behaviour overrides")
    options: Dict[str, Any] = Field(default_factory=dict, description="Additional CCXT client options")

    @model_validator(mode='before')
    def _promote_reserved_options(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        options = values.get('options')
        if not isinstance(options, dict):
            return values

        mapping = {
            'api_key': 'api_key',
            'secret': 'secret',
            'password': 'passphrase',
            'passphrase': 'passphrase',
            'sandbox': 'sandbox',
            'rate_limit': 'rate_limit',
            'enable_rate_limit': 'enable_rate_limit',
            'timeout': 'timeout',
        }

        promoted = dict(options)
        for option_key, target in mapping.items():
            if option_key in promoted and target not in values:
                values[target] = promoted.pop(option_key)

        values['options'] = promoted
        return values

    @field_validator('exchange_id')
    @classmethod
    def _validate_exchange(cls, value: str) -> str:
        return _validate_exchange_id(value)

    @field_validator('api_key', 'secret', 'passphrase', mode='before')
    @classmethod
    def _strip_credentials(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not isinstance(value, str):
            raise TypeError("Credential fields must be strings")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Credential fields cannot be empty strings")
        return stripped

    @model_validator(mode='after')
    def validate_credentials(self) -> 'CcxtConfig':
        if self.api_key and not self.secret:
            raise ValueError("API secret required when API key is provided")
        return self

    def _build_options(self) -> CcxtOptionsConfig:
        reserved = {
            'api_key', 'secret', 'password', 'passphrase',
            'sandbox', 'rate_limit', 'enable_rate_limit', 'timeout'
        }
        extras = {k: v for k, v in self.options.items() if k not in reserved}
        return CcxtOptionsConfig(
            api_key=self.api_key,
            secret=self.secret,
            password=self.passphrase,
            sandbox=self.sandbox,
            rate_limit=self.rate_limit,
            enable_rate_limit=self.enable_rate_limit,
            timeout=self.timeout,
            **extras,
        )

    def to_exchange_config(self) -> 'CcxtExchangeConfig':
        return CcxtExchangeConfig(
            exchange_id=self.exchange_id,
            proxies=self.proxies,
            ccxt_options=self._build_options(),
            transport=self.transport,
        )

    def to_context(self, *, proxy_settings: Optional[ProxySettings] = None) -> 'CcxtExchangeContext':
        from .context import CcxtExchangeContext  # local import to avoid circular dependency

        exchange_config = self.to_exchange_config()
        transport = exchange_config.transport or CcxtTransportConfig()

        http_proxy_url: Optional[str] = None
        websocket_proxy_url: Optional[str] = None

        if self.proxies:
            http_proxy_url = self.proxies.rest
            websocket_proxy_url = self.proxies.websocket
        elif proxy_settings:
            http_proxy = proxy_settings.get_proxy(self.exchange_id, 'http')
            websocket_proxy = proxy_settings.get_proxy(self.exchange_id, 'websocket')
            http_proxy_url = http_proxy.url if http_proxy else None
            websocket_proxy_url = websocket_proxy.url if websocket_proxy else None

        ccxt_options = exchange_config.to_ccxt_dict()

        return CcxtExchangeContext(
            exchange_id=self.exchange_id,
            ccxt_options=ccxt_options,
            transport=transport,
            http_proxy_url=http_proxy_url,
            websocket_proxy_url=websocket_proxy_url,
            use_sandbox=bool(ccxt_options.get('sandbox', False)),
            config=self,
        )


class CcxtExchangeConfig(BaseModel):
    """Complete CCXT exchange configuration with validation."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    exchange_id: str = Field(..., description="CCXT exchange identifier (e.g., 'backpack')")
    proxies: Optional[CcxtProxyConfig] = Field(None, description="Proxy configuration")
    ccxt_options: Optional[CcxtOptionsConfig] = Field(None, description="CCXT client options")
    transport: Optional[CcxtTransportConfig] = Field(None, description="Transport configuration")

    @field_validator('exchange_id')
    @classmethod
    def validate_exchange_id(cls, value: str) -> str:
        return _validate_exchange_id(value)

    @model_validator(mode='after')
    def validate_configuration_consistency(self) -> 'CcxtExchangeConfig':
        if self.ccxt_options and self.ccxt_options.api_key and not self.ccxt_options.secret:
            raise ValueError("API secret required when API key is provided")
        return self

    def to_ccxt_dict(self) -> Dict[str, Any]:
        if not self.ccxt_options:
            return {}

        ccxt_dict = self.ccxt_options.model_dump(exclude_none=True)
        result: Dict[str, Any] = {}

        field_mapping = {
            'api_key': 'apiKey',
            'secret': 'secret',
            'password': 'password',
            'sandbox': 'sandbox',
            'rate_limit': 'rateLimit',
            'enable_rate_limit': 'enableRateLimit',
            'timeout': 'timeout',
        }

        for pydantic_field, ccxt_field in field_mapping.items():
            if pydantic_field in ccxt_dict:
                result[ccxt_field] = ccxt_dict[pydantic_field]

        for field, value in ccxt_dict.items():
            if field not in field_mapping:
                result[field] = value

        return result


__all__ = [
    'CcxtProxyConfig',
    'CcxtOptionsConfig',
    'CcxtTransportConfig',
    'CcxtExchangeConfig',
    'CcxtConfig',
    'CcxtConfigExtensions',
]
