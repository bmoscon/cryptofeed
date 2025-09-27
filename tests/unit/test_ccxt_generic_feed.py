from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from cryptofeed.defines import ORDERS
from cryptofeed.exchanges.ccxt_config import CcxtConfig
from cryptofeed.exchanges.ccxt_generic import CcxtGenericFeed, CcxtRestTransport


class DummyCache:
    def __init__(self, exchange_id: str):
        self.exchange_id = exchange_id

    async def ensure(self) -> None:  # pragma: no cover - no-op for tests
        return

    def request_symbol(self, symbol: str) -> str:
        return symbol


class DummyRestClient:
    def __init__(self, config: Any = None):
        self.config = config or {}

    async def close(self) -> None:
        return

    def check_required_credentials(self) -> None:
        raise ValueError("missing credentials")


@pytest.fixture
def patch_async_support(monkeypatch):
    from cryptofeed.exchanges import ccxt_generic

    original_import = ccxt_generic._dynamic_import

    def fake_import(path: str):
        if path == "ccxt.async_support":
            return SimpleNamespace(backpack=DummyRestClient)
        return original_import(path)

    monkeypatch.setattr(ccxt_generic, "_dynamic_import", fake_import)
    yield
    monkeypatch.setattr(ccxt_generic, "_dynamic_import", original_import)


def test_private_channels_without_credentials_raises():
    context = CcxtConfig(exchange_id="backpack").to_context()

    with pytest.raises(RuntimeError, match="credentials are missing"):
        CcxtGenericFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[ORDERS],
            config_context=context,
        )


def test_auth_callbacks_registered_and_require_auth():
    context = CcxtConfig(exchange_id="backpack", api_key="key", secret="secret").to_context()
    feed = CcxtGenericFeed(
        exchange_id="backpack",
        symbols=["BTC-USDT"],
        channels=[ORDERS],
        config_context=context,
    )

    called = []

    def auth_callback(client):
        called.append(client)

    feed.register_authentication_callback(auth_callback)

    kwargs = feed._rest_transport_kwargs()
    assert kwargs["require_auth"] is True
    assert auth_callback in kwargs["auth_callbacks"]


@pytest.mark.asyncio
async def test_rest_transport_authentication_failure(patch_async_support):
    context = CcxtConfig(exchange_id="backpack").to_context()
    transport = CcxtRestTransport(
        DummyCache("backpack"),
        context=context,
        require_auth=True,
    )

    client = await transport._ensure_client()
    with pytest.raises(RuntimeError, match="invalid or incomplete"):
        await transport._authenticate_client(client)
