from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from cryptofeed.exchanges.backpack.config import BackpackConfig, BackpackAuthSettings


def _hex_key() -> str:
    return "".join(f"{b:02x}" for b in range(32))


def _b64_key() -> str:
    raw = bytes(range(32))
    return base64.b64encode(raw).decode()


def test_enabling_private_channels_requires_auth():
    with pytest.raises(ValueError, match="requires auth credentials"):
        BackpackConfig(enable_private_channels=True)


def test_hex_keys_normalize_successfully():
    config = BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key=_hex_key(),
            private_key=_hex_key(),
        ),
    )

    assert config.enable_private_channels is True
    assert config.auth is not None
    assert config.auth.public_key_b64 == base64.b64encode(bytes(range(32))).decode()


def test_base64_keys_are_accepted_and_normalized():
    config = BackpackConfig(
        enable_private_channels=True,
        auth=BackpackAuthSettings(
            api_key="api",
            public_key=_b64_key(),
            private_key=_b64_key(),
        ),
    )

    assert config.auth is not None
    assert config.auth.private_key_b64 == _b64_key()


@pytest.mark.parametrize("window_ms", [0, 20000])
def test_window_bounds_enforced(window_ms):
    with pytest.raises(ValidationError):
        BackpackConfig(
            enable_private_channels=False,
            window_ms=window_ms,
        )


def test_public_only_config_defaults():
    config = BackpackConfig()

    assert config.enable_private_channels is False
    assert config.auth is None
    assert config.rest_endpoint == "https://api.backpack.exchange"
    assert config.ws_endpoint == "wss://ws.backpack.exchange"


def test_rejects_legacy_native_enabled_field():
    with pytest.raises(ValueError, match="no longer supported"):
        BackpackConfig(native_enabled=True)
