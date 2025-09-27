"""CCXT configuration models, loaders, and runtime context helpers."""
from __future__ import annotations

import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Union

import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

from cryptofeed.proxy import ProxySettings


LOG = logging.getLogger('feedhandler')


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


def _validate_exchange_id(value: str) -> str:
    """Validate exchange id follows lowercase/slim format."""
    if not value or not isinstance(value, str):
        raise ValueError("Exchange ID must be a non-empty string")
    if not value.islower() or not value.replace('_', '').replace('-', '').isalnum():
        raise ValueError("Exchange ID must be lowercase alphanumeric with optional underscores/hyphens")
    return value.strip()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dictionaries without mutating inputs."""
    if not override:
        return base
    result = deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _assign_path(data: Dict[str, Any], path: list[str], value: Any) -> None:
    key = path[0].lower().replace('-', '_')
    if len(path) == 1:
        data[key] = value
        return
    child = data.setdefault(key, {})
    if not isinstance(child, dict):
        raise ValueError(f"Cannot override non-dict config section: {key}")
    _assign_path(child, path[1:], value)


def _extract_env_values(exchange_id: str, env: Mapping[str, str]) -> Dict[str, Any]:
    prefix = f"CRYPTOFEED_CCXT_{exchange_id.upper()}__"
    result: Dict[str, Any] = {}
    for key, value in env.items():
        if not key.startswith(prefix):
            continue
        path = key[len(prefix):].split('__')
        _assign_path(result, path, value)
    return result


class CcxtConfigExtensions:
    """Registry for exchange-specific configuration hooks."""

    _hooks: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    @classmethod
    def register(cls, exchange_id: str, hook: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """Register hook to mutate raw configuration prior to validation."""
        cls._hooks[exchange_id] = hook

    @classmethod
    def apply(cls, exchange_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        hook = cls._hooks.get(exchange_id)
        if hook is None:
            return data
        try:
            working = deepcopy(data)
            updated = hook(working)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOG.error("Failed applying CCXT config extension for %s: %s", exchange_id, exc)
            raise
        if updated is None:
            return working
        if isinstance(updated, dict):
            return updated
        return data

    @classmethod
    def reset(cls) -> None:
        cls._hooks.clear()


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
            if option_key in promoted:
                value = promoted.pop(option_key)
                if target not in values:
                    values[target] = value

        values['options'] = promoted
        return values

    @field_validator('exchange_id')
    @classmethod
    def _validate_exchange_id(cls, value: str) -> str:
        return _validate_exchange_id(value)

    @model_validator(mode='after')
    def validate_credentials(self) -> 'CcxtConfig':
        if self.api_key and not self.secret:
            raise ValueError("API secret required when API key is provided")
        return self

    def _build_options(self) -> CcxtOptionsConfig:
        reserved = {'api_key', 'secret', 'password', 'passphrase', 'sandbox', 'rate_limit', 'enable_rate_limit', 'timeout'}
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


@dataclass(frozen=True)
class CcxtExchangeContext:
    """Runtime view of CCXT configuration for an exchange."""

    exchange_id: str
    ccxt_options: Dict[str, Any]
    transport: CcxtTransportConfig
    http_proxy_url: Optional[str]
    websocket_proxy_url: Optional[str]
    use_sandbox: bool
    config: CcxtConfig

    @property
    def timeout(self) -> Optional[int]:
        return self.ccxt_options.get('timeout')

    @property
    def rate_limit(self) -> Optional[int]:
        return self.ccxt_options.get('rateLimit')


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
        """Convert to dictionary format expected by CCXT clients."""
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


# Convenience function for backward compatibility
def validate_ccxt_config(
    exchange_id: str,
    proxies: Optional[Dict[str, str]] = None,
    ccxt_options: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> CcxtExchangeConfig:
    """Validate and convert legacy dict-based config to typed Pydantic model."""

    data: Dict[str, Any] = {'exchange_id': exchange_id}

    if proxies:
        data['proxies'] = proxies

    option_extras: Dict[str, Any] = {}
    if ccxt_options:
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
        for key, value in ccxt_options.items():
            target = mapping.get(key)
            if target:
                data[target] = value
            else:
                option_extras[key] = value

    transport_fields = {'snapshot_interval', 'websocket_enabled', 'rest_only', 'use_market_id'}
    transport_kwargs = {k: v for k, v in kwargs.items() if k in transport_fields}
    remaining_kwargs = {k: v for k, v in kwargs.items() if k not in transport_fields}

    if transport_kwargs:
        data['transport'] = transport_kwargs

    if option_extras or remaining_kwargs:
        data['options'] = _deep_merge(option_extras, remaining_kwargs)

    data = CcxtConfigExtensions.apply(exchange_id, data)

    config = CcxtConfig(**data)
    return config.to_exchange_config()


def load_ccxt_config(
    exchange_id: str,
    *,
    yaml_path: Optional[Union[str, Path]] = None,
    overrides: Optional[Dict[str, Any]] = None,
    proxy_settings: Optional[ProxySettings] = None,
    env: Optional[Mapping[str, str]] = None,
) -> CcxtExchangeContext:
    """Load CCXT configuration from YAML, environment, and overrides."""

    data: Dict[str, Any] = {'exchange_id': exchange_id}

    if yaml_path:
        path = Path(yaml_path)
        if not path.exists():
            raise FileNotFoundError(f"CCXT config YAML not found: {path}")
        yaml_data = yaml.safe_load(path.read_text()) or {}
        exchange_yaml = yaml_data.get('exchanges', {}).get(exchange_id, {})
        data = _deep_merge(data, exchange_yaml)

    env_map = env or os.environ
    env_values = _extract_env_values(exchange_id, env_map)
    if env_values:
        data = _deep_merge(data, env_values)

    if overrides:
        data = _deep_merge(data, overrides)

    data = CcxtConfigExtensions.apply(exchange_id, data)

    config = CcxtConfig(**data)
    return config.to_context(proxy_settings=proxy_settings)


__all__ = [
    'CcxtProxyConfig',
    'CcxtOptionsConfig',
    'CcxtTransportConfig',
    'CcxtConfig',
    'CcxtExchangeContext',
    'CcxtConfigExtensions',
    'CcxtExchangeConfig',
    'load_ccxt_config',
    'validate_ccxt_config'
]
