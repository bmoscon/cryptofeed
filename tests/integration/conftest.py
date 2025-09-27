from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, List

import pytest


class _FakeAsyncClient:
    def __init__(self, registry: Dict[str, List["_FakeAsyncClient"]], **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self._registry = registry
        registry.setdefault("rest", []).append(self)

    async def load_markets(self):
        return {"BTC/USDT": {"id": "BTC/USDT"}}

    async def fetch_order_book(self, symbol, limit=None):
        return {
            "symbol": symbol,
            "timestamp": 1_700_000_000_000,
            "bids": [["100.1", "1.5"], ["100.0", "0.25"]],
            "asks": [["100.3", "1.0"], ["100.4", "0.75"]],
            "nonce": 1234,
        }

    async def close(self):
        self.closed = True

    def check_required_credentials(self):
        if not self.kwargs.get("apiKey") or not self.kwargs.get("secret"):
            raise ValueError("missing credentials")


class _FakeProClient(_FakeAsyncClient):
    def __init__(self, registry: Dict[str, List["_FakeAsyncClient"]], **kwargs):
        super().__init__(registry, **kwargs)
        registry.setdefault("ws", []).append(self)

    async def watch_trades(self, symbol):
        return [
            {
                "symbol": symbol,
                "price": "101.25",
                "p": "101.25",
                "amount": "0.75",
                "q": "0.75",
                "timestamp": 1_700_000_010_000,
                "ts": 1_700_000_010_000,
                "side": "buy",
                "id": "trade-1",
                "t": "trade-1",
                "s": 4321,
                "sequence": 4321,
            }
        ]


@pytest.fixture(scope="function")
def ccxt_fake_clients(monkeypatch) -> Dict[str, List[_FakeAsyncClient]]:
    """Patch CCXT dynamic imports with deterministic fake clients."""

    from cryptofeed.exchanges.ccxt import generic as generic_module

    registry: Dict[str, List[_FakeAsyncClient]] = {"rest": [], "ws": []}

    def make_async(*args, **kwargs):
        if args:
            if isinstance(args[0], dict):
                kwargs = {**args[0], **kwargs}
        return _FakeAsyncClient(registry, **kwargs)

    def make_pro(*args, **kwargs):
        if args:
            if isinstance(args[0], dict):
                kwargs = {**args[0], **kwargs}
        return _FakeProClient(registry, **kwargs)

    def importer(path: str):
        if path == "ccxt.async_support":
            return SimpleNamespace(backpack=make_async)
        if path == "ccxt.pro":
            return SimpleNamespace(backpack=make_pro)
        raise ImportError(path)

    original_resolver = generic_module._resolve_dynamic_import
    original_import = generic_module._dynamic_import
    monkeypatch.setattr(generic_module, "_resolve_dynamic_import", lambda: importer)
    monkeypatch.setattr(generic_module, "_dynamic_import", importer)

    yield registry

    monkeypatch.setattr(generic_module, "_resolve_dynamic_import", original_resolver)
    monkeypatch.setattr(generic_module, "_dynamic_import", original_import)
