from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

import pytest


class _FakeAsyncClient:
    def __init__(
        self,
        registry: Dict[str, List["_FakeAsyncClient"]],
        *,
        exchange_id: str = "backpack",
        **kwargs,
    ) -> None:
        self.kwargs = kwargs
        self.closed = False
        self._registry = registry
        self.exchange_id = exchange_id
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
    def __init__(
        self,
        registry: Dict[str, List["_FakeAsyncClient"]],
        *,
        exchange_id: str = "backpack",
        **kwargs,
    ) -> None:
        super().__init__(registry, exchange_id=exchange_id, **kwargs)
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


HYPERLIQUID_MARKETS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "ccxt" / "hyperliquid_markets.json").read_text()
)


class _HyperliquidAsyncClient(_FakeAsyncClient):
    def __init__(self, registry: Dict[str, List["_FakeAsyncClient"]], **kwargs) -> None:
        super().__init__(registry, exchange_id="hyperliquid", **kwargs)

    async def load_markets(self):
        return HYPERLIQUID_MARKETS

    async def fetch_order_book(self, symbol, limit=None):
        return {
            "symbol": symbol,
            "timestamp": 1_700_300_000_000,
            "bids": [["25000.4", "4.2"], ["25000.0", "1.0"]],
            "asks": [["25000.8", "3.1"], ["25001.0", "2.2"]],
            "nonce": 901,
        }


class _HyperliquidProClient(_HyperliquidAsyncClient):
    def __init__(self, registry: Dict[str, List["_FakeAsyncClient"]], **kwargs) -> None:
        super().__init__(registry, **kwargs)
        registry.setdefault("ws", []).append(self)

    async def watch_trades(self, symbol):
        return [
            {
                "symbol": symbol,
                "price": "25001.1",
                "amount": "0.8",
                "timestamp": 1_700_300_050_000,
                "side": "buy",
                "id": "hl-trade-7",
                "sequence": 1337,
            }
        ]


@pytest.fixture(scope="function")
def ccxt_fake_clients(monkeypatch) -> Dict[str, List[_FakeAsyncClient]]:
    """Patch CCXT dynamic imports with deterministic fake clients."""

    from cryptofeed.exchanges.ccxt import generic as generic_module
    from cryptofeed.exchanges.ccxt import transport as transport_pkg
    from cryptofeed.exchanges.ccxt.transport import rest as rest_module
    from cryptofeed.exchanges.ccxt.transport import ws as ws_module

    registry: Dict[str, List[_FakeAsyncClient]] = {"rest": [], "ws": []}

    def _merge_kwargs(args, kwargs):
        if args and isinstance(args[0], dict):
            return {**args[0], **kwargs}
        return kwargs

    def make_async_factory(client_cls):
        def factory(*args, **kwargs):
            params = _merge_kwargs(args, kwargs)
            return client_cls(registry, **params)

        return factory

    def importer(path: str):
        if path == "ccxt.async_support":
            return SimpleNamespace(
                backpack=make_async_factory(lambda registry, **kwargs: _FakeAsyncClient(
                    registry, exchange_id="backpack", **kwargs
                )),
                hyperliquid=make_async_factory(_HyperliquidAsyncClient),
            )
        if path == "ccxt.pro":
            return SimpleNamespace(
                backpack=make_async_factory(
                    lambda registry, **kwargs: _FakeProClient(
                        registry, exchange_id="backpack", **kwargs
                    )
                ),
                hyperliquid=make_async_factory(_HyperliquidProClient),
            )
        raise ImportError(path)

    original_resolver = generic_module._resolve_dynamic_import
    original_import = generic_module._dynamic_import
    original_rest_resolver = getattr(rest_module, "_resolve_dynamic_import", None)
    original_ws_resolver = getattr(ws_module, "_resolve_dynamic_import", None)

    monkeypatch.setattr(generic_module, "_resolve_dynamic_import", lambda: importer)
    monkeypatch.setattr(generic_module, "_dynamic_import", importer)
    if original_rest_resolver is not None:
        monkeypatch.setattr(rest_module, "_resolve_dynamic_import", lambda: importer)
    if original_ws_resolver is not None:
        monkeypatch.setattr(ws_module, "_resolve_dynamic_import", lambda: importer)
    if hasattr(transport_pkg, "_resolve_dynamic_import"):
        monkeypatch.setattr(transport_pkg, "_resolve_dynamic_import", lambda: importer)

    yield registry

    monkeypatch.setattr(generic_module, "_resolve_dynamic_import", original_resolver)
    monkeypatch.setattr(generic_module, "_dynamic_import", original_import)
