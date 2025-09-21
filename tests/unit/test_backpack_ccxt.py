"""Unit tests for the Backpack ccxt integration scaffolding."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
import sys

import pytest


@pytest.fixture(autouse=True)
def clear_ccxt_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ccxt modules are absent unless explicitly injected."""
    for name in [
        "ccxt",
        "ccxt.async_support",
        "ccxt.async_support.backpack",
        "ccxt.pro",
        "ccxt.pro.backpack",
    ]:
        monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.fixture
def fake_ccxt(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    markets = {
        "BTC/USDT": {
            "id": "BTC_USDT",
            "symbol": "BTC/USDT",
            "limits": {"amount": {"min": 0.0001}},
            "precision": {"price": 2, "amount": 6},
        }
    }

    class FakeAsyncClient:
        def __init__(self) -> None:
            self.markets = markets
            self.rateLimit = 100

        async def load_markets(self) -> dict[str, Any]:
            return markets

        async def fetch_order_book(self, symbol: str, limit: int | None = None) -> dict[str, Any]:
            assert symbol == "BTC_USDT"
            return {
                "bids": [["30000", "1.5"], ["29950", "2"]],
                "asks": [["30010", "1.25"], ["30020", "3"]],
                "timestamp": 1_700_000_000_000,
            }

        async def close(self) -> None:
            return None

    class FakeProClient:
        def __init__(self) -> None:
            self._responses: list[list[dict[str, Any]]] = []

        async def watch_trades(self, symbol: str) -> list[dict[str, Any]]:
            assert symbol == "BTC_USDT"
            if self._responses:
                return self._responses.pop(0)
            raise asyncio.TimeoutError

        async def watch_order_book(self, symbol: str) -> dict[str, Any]:
            assert symbol == "BTC_USDT"
            return {
                "bids": [["30000", "1.5", 1001]],
                "asks": [["30010", "1.0", 1001]],
                "timestamp": 1_700_000_000_500,
                "nonce": 1001,
            }

        async def close(self) -> None:
            return None

    fake_async_support = SimpleNamespace(backpack=FakeAsyncClient)
    fake_pro = SimpleNamespace(backpack=FakeProClient)
    fake_root = SimpleNamespace(async_support=fake_async_support, pro=fake_pro)

    import sys

    monkeypatch.setitem(sys.modules, "ccxt", fake_root)
    monkeypatch.setitem(sys.modules, "ccxt.async_support", fake_async_support)
    monkeypatch.setitem(sys.modules, "ccxt.async_support.backpack", FakeAsyncClient)
    monkeypatch.setitem(sys.modules, "ccxt.pro", fake_pro)
    monkeypatch.setitem(sys.modules, "ccxt.pro.backpack", FakeProClient)

    return SimpleNamespace(async_client=FakeAsyncClient, pro_client=FakeProClient, markets=markets)


@pytest.mark.asyncio
async def test_metadata_cache_loads_markets(fake_ccxt):
    from cryptofeed.exchanges.backpack_ccxt import BackpackMetadataCache

    cache = BackpackMetadataCache()
    await cache.ensure()

    assert cache.id_for_symbol("BTC-USDT") == "BTC_USDT"
    assert Decimal("0.0001") == cache.min_amount("BTC-USDT")


@pytest.mark.asyncio
async def test_rest_transport_normalizes_order_book(fake_ccxt):
    from cryptofeed.exchanges.backpack_ccxt import BackpackMetadataCache, BackpackRestTransport

    cache = BackpackMetadataCache()
    await cache.ensure()

    async with BackpackRestTransport(cache) as rest:
        snapshot = await rest.order_book("BTC-USDT", limit=2)

    assert snapshot.symbol == "BTC-USDT"
    assert snapshot.sequence is None
    assert snapshot.timestamp == pytest.approx(1_700_000_000.0)
    assert snapshot.bids[0] == (Decimal("30000"), Decimal("1.5"))
    assert snapshot.asks[0] == (Decimal("30010"), Decimal("1.25"))


@pytest.mark.asyncio
async def test_ws_transport_normalizes_trade(fake_ccxt, monkeypatch):
    from cryptofeed.exchanges.backpack_ccxt import BackpackMetadataCache, BackpackWsTransport

    cache = BackpackMetadataCache()
    await cache.ensure()

    transport = BackpackWsTransport(cache)
    client = transport._ensure_client()
    client._responses.append(
        [
            {
                "p": "30005",
                "q": "0.25",
                "ts": 1_700_000_000_123,
                "s": 42,
                "t": "tradeid",
                "side": "buy",
            }
        ]
    )

    trade = await transport.next_trade("BTC-USDT")
    assert trade.symbol == "BTC-USDT"
    assert trade.price == Decimal("30005")
    assert trade.amount == Decimal("0.25")
    assert trade.sequence == 42
    assert trade.timestamp == pytest.approx(1_700_000_000.123)

    await transport.close()
