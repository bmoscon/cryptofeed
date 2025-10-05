"""Runtime context utilities for CCXT configuration."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import yaml

from cryptofeed.proxy import ProxySettings

from .config import CcxtConfig, CcxtExchangeConfig, CcxtOptionsConfig, CcxtProxyConfig, CcxtTransportConfig
from .extensions import CcxtConfigExtensions

LOG = logging.getLogger("feedhandler")


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge dictionaries without mutating inputs."""

    if not override:
        return base
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
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
        return self.ccxt_options.get("timeout")

    @property
    def rate_limit(self) -> Optional[int]:
        return self.ccxt_options.get("rateLimit")


def validate_ccxt_config(
    exchange_id: str,
    proxies: Optional[Dict[str, str]] = None,
    ccxt_options: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> CcxtExchangeConfig:
    """Validate and convert legacy dict-based config to typed Pydantic model."""

    data: Dict[str, Any] = {"exchange_id": exchange_id}

    if proxies:
        data["proxies"] = proxies

    option_extras: Dict[str, Any] = {}
    if ccxt_options:
        mapping = {
            "api_key": "api_key",
            "secret": "secret",
            "password": "passphrase",
            "passphrase": "passphrase",
            "sandbox": "sandbox",
            "rate_limit": "rate_limit",
            "enable_rate_limit": "enable_rate_limit",
            "timeout": "timeout",
        }
        for key, value in ccxt_options.items():
            target = mapping.get(key)
            if target:
                data[target] = value
            else:
                option_extras[key] = value

    transport_fields = {"snapshot_interval", "websocket_enabled", "rest_only", "use_market_id"}
    transport_kwargs = {k: v for k, v in kwargs.items() if k in transport_fields}
    remaining_kwargs = {k: v for k, v in kwargs.items() if k not in transport_fields}

    if transport_kwargs:
        data["transport"] = transport_kwargs

    if option_extras or remaining_kwargs:
        data["options"] = _deep_merge(option_extras, remaining_kwargs)

    data = CcxtConfigExtensions.apply(exchange_id, data)
    config = CcxtConfig(**data)
    return config.to_exchange_config()


def load_ccxt_config(
    exchange_id: str,
    *,
    yaml_path: Optional[Path] = None,
    overrides: Optional[Dict[str, Any]] = None,
    proxy_settings: Optional[ProxySettings] = None,
) -> CcxtExchangeContext:
    """Load CCXT configuration from YAML/environment/overrides."""

    data: Dict[str, Any] = {"exchange_id": exchange_id}

    if yaml_path and yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_data = yaml.safe_load(file) or {}
            exchange_data = yaml_data.get("exchanges", {}).get(exchange_id, {})
            data = _deep_merge(data, exchange_data)

    env_values = _extract_env_values(exchange_id, os.environ)
    data = _deep_merge(data, env_values)

    if overrides:
        data = _deep_merge(data, overrides)

    data = CcxtConfigExtensions.apply(exchange_id, data)
    config = CcxtConfig(**data)
    return config.to_context(proxy_settings=proxy_settings)


__all__ = [
    "CcxtExchangeContext",
    "load_ccxt_config",
    "validate_ccxt_config",
]
