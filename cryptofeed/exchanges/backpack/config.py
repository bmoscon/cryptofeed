from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from cryptofeed.proxy import ProxyConfig


BACKPACK_REST_PROD = "https://api.backpack.exchange"
BACKPACK_WS_PROD = "wss://ws.backpack.exchange"
BACKPACK_REST_SANDBOX = "https://api.backpack.exchange/sandbox"
BACKPACK_WS_SANDBOX = "wss://ws.backpack.exchange/sandbox"


def _normalize_key(value: str) -> str:
    value = value.strip()
    # Try hex decoding first
    try:
        raw = bytes.fromhex(value)
        if len(raw) != 32:
            raise ValueError
        return base64.b64encode(raw).decode()
    except (ValueError, binascii.Error):
        pass

    # Try base64 decoding
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32:
            raise ValueError
        return base64.b64encode(raw).decode()
    except (ValueError, binascii.Error):
        raise ValueError("Backpack keys must be 32-byte hex or base64 strings") from None


class BackpackAuthSettings(BaseModel):
    """Authentication credentials required for Backpack private channels."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    api_key: str = Field(..., min_length=1, description="Backpack API key")
    public_key: str = Field(..., min_length=1, description="ED25519 public key (hex or base64)")
    private_key: str = Field(..., min_length=1, description="ED25519 private key seed (hex or base64)")
    passphrase: Optional[str] = Field(None, description="Optional Backpack passphrase")

    @field_validator('public_key', 'private_key')
    @classmethod
    def normalize_keys(cls, value: str) -> str:
        return _normalize_key(value)

    @property
    def public_key_b64(self) -> str:
        return self.public_key

    @property
    def private_key_b64(self) -> str:
        return self.private_key

    @property
    def private_key_bytes(self) -> bytes:
        return base64.b64decode(self.private_key_b64)


class BackpackConfig(BaseModel):
    """Configuration for native Backpack feed integration."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    legacy_fields: ClassVar[set[str]] = {
        'native_enabled',
        'ccxt',
        'rest_endpoint_override',
        'ws_endpoint_override',
        'rest_endpoint',
        'ws_endpoint',
    }

    @model_validator(mode='before')
    @classmethod
    def _reject_legacy_fields(cls, data):
        if isinstance(data, dict):
            invalid = sorted(field for field in data.keys() if field in cls.legacy_fields)
            if invalid:
                joined = ", ".join(invalid)
                raise ValueError(f"Backpack configuration fields {joined} are no longer supported; use native options.")
        return data

    exchange_id: Literal['backpack'] = Field('backpack', description="Exchange identifier")
    enable_private_channels: bool = Field(False, description="Enable private Backpack channels")
    window_ms: int = Field(5000, ge=1, le=10_000, description="Auth window in milliseconds")
    use_sandbox: bool = Field(False, description="Use Backpack sandbox endpoints")
    proxies: Optional[ProxyConfig] = Field(None, description="Proxy configuration overrides")
    auth: Optional[BackpackAuthSettings] = Field(None, description="Authentication credentials")

    @model_validator(mode='after')
    def validate_private_channels(self) -> 'BackpackConfig':
        if self.enable_private_channels and self.auth is None:
            raise ValueError("enable_private_channels=True requires auth credentials")
        return self

    @property
    def rest_endpoint(self) -> str:
        return BACKPACK_REST_SANDBOX if self.use_sandbox else BACKPACK_REST_PROD

    @property
    def ws_endpoint(self) -> str:
        return BACKPACK_WS_SANDBOX if self.use_sandbox else BACKPACK_WS_PROD

    @property
    def requires_auth(self) -> bool:
        return self.enable_private_channels
