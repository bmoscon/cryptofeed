"""Unit tests for the CCXT REST transport."""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock


from cryptofeed.exchanges.ccxt.transport.rest import CcxtRestTransport


class DummyCache:
    """Minimal metadata cache stub for tests."""

    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id
        self.ensure_calls = 0

    async def ensure(self) -> None:
        self.ensure_calls += 1

    def request_symbol(self, symbol: str) -> str:
        return symbol


class DummyContext:
    """Context stub exposing ccxt options and proxy URLs."""

    def __init__(self, *, http_proxy_url: str | None = None) -> None:
        self.http_proxy_url = http_proxy_url
        self.websocket_proxy_url = None
        self.ccxt_options = {"timeout": 30}


@pytest.fixture
def cache() -> DummyCache:
    return DummyCache("test-exchange")


def test_client_kwargs_prefers_context_proxy(monkeypatch, cache: DummyCache) -> None:
    """Transport should prioritise proxy URL defined in the context."""

    context = DummyContext(http_proxy_url="http://context-proxy:8080")

    transport = CcxtRestTransport(cache, context=context)

    # Monkeypatch injector to raise if consulted so we ensure context path is followed
    class DummyInjector:
        def get_http_proxy_url(self, exchange_id: str) -> str:  # pragma: nocover - should not be called
            raise AssertionError("Injector should not be queried when context provides proxy")

    monkeypatch.setattr(
        "cryptofeed.exchanges.ccxt.transport.rest.get_proxy_injector",
        lambda: DummyInjector(),
    )

    kwargs = transport._client_kwargs()

    assert kwargs["aiohttp_proxy"] == "http://context-proxy:8080"
    assert kwargs["proxies"] == {
        "http": "http://context-proxy:8080",
        "https": "http://context-proxy:8080",
    }


def test_client_kwargs_falls_back_to_injector(monkeypatch, cache: DummyCache) -> None:
    """When no proxy is in context the global injector should be consulted."""

    recorded_exchange_ids: list[str] = []

    class DummyInjector:
        def get_http_proxy_url(self, exchange_id: str) -> str | None:
            recorded_exchange_ids.append(exchange_id)
            return "http://injector-proxy:9090"

    monkeypatch.setattr(
        "cryptofeed.exchanges.ccxt.transport.rest.get_proxy_injector",
        lambda: DummyInjector(),
    )

    transport = CcxtRestTransport(cache, context=None)

    kwargs = transport._client_kwargs()

    assert recorded_exchange_ids == ["test-exchange"]
    assert kwargs["aiohttp_proxy"] == "http://injector-proxy:9090"
    assert kwargs["proxies"] == {
        "http": "http://injector-proxy:9090",
        "https": "http://injector-proxy:9090",
    }


@pytest.mark.asyncio
async def test_order_book_retries_on_transient_error(monkeypatch, cache: DummyCache, caplog: pytest.LogCaptureFixture) -> None:
    """Transient failures should trigger retries with backoff and logging."""

    transport = CcxtRestTransport(
        cache,
        context=None,
        max_retries=2,
        base_retry_delay=0.01,
    )

    attempt_counter = {"count": 0}

    async def fetch_order_book(symbol: str, *, limit: int | None = None) -> dict:
        attempt_counter["count"] += 1
        if attempt_counter["count"] == 1:
            raise RuntimeError("transient failure")
        return {
            "bids": [("50000", "1.5")],
            "asks": [("50010", "1.0")],
            "timestamp": 1700000000000,
            "nonce": 42,
        }

    dummy_client = SimpleNamespace(
        fetch_order_book=AsyncMock(side_effect=fetch_order_book),
        close=AsyncMock(),
    )

    async def fake_sleep(delay: float) -> None:
        assert delay >= 0

    transport._client = dummy_client
    monkeypatch.setattr(transport, "_ensure_client", AsyncMock(return_value=dummy_client))
    monkeypatch.setattr(transport, "_sleep", fake_sleep)

    with caplog.at_level(logging.WARNING):
        snapshot = await transport.order_book("BTC-USD")

    assert attempt_counter["count"] == 2
    assert snapshot.symbol == "BTC-USD"
    assert snapshot.sequence == 42
    assert "retry" in " ".join(record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_close_cleans_up_client(cache: DummyCache) -> None:
    """Closing the transport should close the underlying client and reset it."""

    dummy_client = SimpleNamespace(close=AsyncMock())
    transport = CcxtRestTransport(cache, context=None)
    transport._client = dummy_client

    await transport.close()

    assert transport._client is None
    dummy_client.close.assert_awaited_once()

