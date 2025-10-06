"""Unit tests for the CCXT WebSocket transport."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from cryptofeed.exchanges.ccxt.generic import CcxtUnavailable
from cryptofeed.exchanges.ccxt.transport.ws import CcxtWsTransport


class DummyCache:
    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id
        self.ensure_calls = 0

    async def ensure(self) -> None:
        self.ensure_calls += 1

    def request_symbol(self, symbol: str) -> str:
        return symbol


class DummyContext:
    def __init__(self, *, websocket_proxy_url: str | None = None, http_proxy_url: str | None = None) -> None:
        self.websocket_proxy_url = websocket_proxy_url
        self.http_proxy_url = http_proxy_url
        self.ccxt_options = {}


@pytest.fixture
def cache() -> DummyCache:
    return DummyCache("test-exchange")


def test_client_kwargs_prefers_websocket_proxy(monkeypatch, cache: DummyCache) -> None:
    seen: dict[str, str] = {}

    def record_proxy(**kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(
        "cryptofeed.exchanges.ccxt.transport.ws.log_proxy_usage",
        lambda **kwargs: record_proxy(**kwargs),
    )

    context = DummyContext(websocket_proxy_url="socks5://context-proxy:1080")
    transport = CcxtWsTransport(cache, context=context)

    kwargs = transport._client_kwargs()

    assert kwargs["aiohttp_proxy"] == "socks5://context-proxy:1080"
    assert kwargs["proxies"] == {
        "http": "socks5://context-proxy:1080",
        "https": "socks5://context-proxy:1080",
    }
    assert seen == {
        "transport": "websocket",
        "exchange_id": "test-exchange",
        "proxy_url": "socks5://context-proxy:1080",
    }


def test_client_kwargs_uses_injector_when_context_missing(monkeypatch, cache: DummyCache) -> None:
    requested: list[str] = []

    class DummyInjector:
        def get_http_proxy_url(self, exchange_id: str) -> str | None:
            requested.append(exchange_id)
            return "http://injector-proxy:8080"

    monkeypatch.setattr(
        "cryptofeed.exchanges.ccxt.transport.ws.get_proxy_injector",
        lambda: DummyInjector(),
    )

    transport = CcxtWsTransport(cache, context=None)
    kwargs = transport._client_kwargs()

    assert requested == ["test-exchange"]
    assert kwargs["aiohttp_proxy"] == "http://injector-proxy:8080"
    assert kwargs["proxies"]["https"] == "http://injector-proxy:8080"


@pytest.mark.asyncio
async def test_next_trade_reconnects_on_transient_failure(monkeypatch, cache: DummyCache) -> None:
    transport = CcxtWsTransport(
        cache,
        context=None,
        max_reconnects=2,
        reconnect_delay=0.0,
    )

    responses = [
        ConnectionError("temporary disconnect"),
        [
            {
                "price": "25000",
                "amount": "0.2",
                "timestamp": 1700000000,
                "side": "buy",
                "id": "trade-1",
            }
        ],
    ]

    first_client = SimpleNamespace(
        watch_trades=AsyncMock(side_effect=lambda *args, **kwargs: _pop_response(responses)),
        close=AsyncMock(),
    )
    second_client = SimpleNamespace(
        watch_trades=AsyncMock(side_effect=lambda *args, **kwargs: _pop_response(responses)),
        close=AsyncMock(),
    )

    sequence = iter([first_client, second_client])

    def fake_ensure_client():
        client = next(sequence)
        transport._client = client
        transport.connect_count += 1
        return client

    monkeypatch.setattr(transport, "_ensure_client", fake_ensure_client)
    monkeypatch.setattr(transport, "_sleep", AsyncMock())

    trade = await transport.next_trade("BTC-USDT")

    assert isinstance(trade.price, Decimal)
    assert transport.reconnect_count == 1
    assert transport.connect_count == 2
    assert first_client.close.await_count == 1


@pytest.mark.asyncio
async def test_next_trade_raises_unavailable_when_not_supported(monkeypatch, cache: DummyCache) -> None:
    transport = CcxtWsTransport(cache, context=None)

    failing_client = SimpleNamespace(
        watch_trades=AsyncMock(side_effect=NotImplementedError("ws not supported")),
        close=AsyncMock(),
    )

    def fake_ensure_client():
        transport._client = failing_client
        transport.connect_count += 1
        return failing_client

    monkeypatch.setattr(transport, "_ensure_client", fake_ensure_client)

    with pytest.raises(CcxtUnavailable):
        await transport.next_trade("BTC-USDT")


def _pop_response(responses):
    response = responses.pop(0)
    if isinstance(response, Exception):
        raise response
    return response
