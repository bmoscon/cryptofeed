from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from cryptofeed.exchanges.ccxt.adapters import get_adapter_registry
from cryptofeed.exchanges.ccxt.generic import CcxtMetadataCache


@pytest.fixture
def hyperliquid_markets() -> dict:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "ccxt" / "hyperliquid_markets.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def patch_hyperliquid(monkeypatch, hyperliquid_markets):
    from cryptofeed.exchanges.ccxt import generic as generic_module

    class DummyClient:
        def __init__(self, *_args, **_kwargs):
            self._closed = False

        async def load_markets(self):
            return hyperliquid_markets

        async def close(self):
            self._closed = True

    def importer(path: str):
        if path == "ccxt.async_support":
            return SimpleNamespace(hyperliquid=lambda **kwargs: DummyClient())
        raise ImportError(path)

    original_import = generic_module._dynamic_import
    monkeypatch.setattr(generic_module, "_dynamic_import", importer)
    yield
    monkeypatch.setattr(generic_module, "_dynamic_import", original_import)


@pytest.mark.asyncio
async def test_metadata_cache_normalizes_hyperliquid_symbols(patch_hyperliquid):
    cache = CcxtMetadataCache("hyperliquid")
    await cache.ensure()

    assert cache.id_for_symbol("BTC-USDT-PERP") == "BTCUSDT"
    assert cache.request_symbol("BTC-USDT-PERP") == "BTC/USDT:USDT"

    market = cache.market_metadata("ETH-USDT-PERP")
    assert market["type"] == "swap"
    assert market["precision"]["price"] == 0.01
    assert cache.min_amount("ETH-USDT-PERP") == Decimal("0.01")


def test_trade_adapter_normalizes_hyperliquid_symbols():
    registry = get_adapter_registry()

    trade = {
        "symbol": "BTC/USDT:USDT",
        "side": "buy",
        "amount": "0.5",
        "price": "25000.5",
        "timestamp": 1_700_000_000_000,
        "id": "trade-42",
    }

    converted = registry.convert_trade("hyperliquid", trade)
    assert converted is not None
    assert converted.symbol == "BTC-USDT-PERP"
    assert converted.price == Decimal("25000.5")
    assert converted.timestamp == pytest.approx(1_700_000_000.0)
