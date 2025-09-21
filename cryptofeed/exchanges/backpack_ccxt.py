"""ccxt-based integration scaffolding for Backpack exchange.

This module provides thin wrappers around ``ccxt`` / ``ccxt.pro`` so that future
feed classes can reuse a consistent transport layer while obeying SOLID/KISS
principles. The implementation intentionally avoids importing ccxt at module
import time to keep the dependency optional.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger


@dataclass(slots=True)
class OrderBookSnapshot:
    symbol: str
    bids: List[Tuple[Decimal, Decimal]]
    asks: List[Tuple[Decimal, Decimal]]
    timestamp: Optional[float]
    sequence: Optional[int]


@dataclass(slots=True)
class TradeUpdate:
    symbol: str
    price: Decimal
    amount: Decimal
    side: Optional[str]
    trade_id: str
    timestamp: float
    sequence: Optional[int]


class CcxtUnavailable(RuntimeError):
    """Raised when ccxt/ccxt.pro cannot be imported."""


def _import_module(path: str) -> Any:
    module = __import__(path)
    for chunk in path.split(".")[1:]:
        module = getattr(module, chunk)
    return module


def _load_async_client() -> Callable[[], Any]:
    try:
        async_support = _import_module("ccxt.async_support")
        return getattr(async_support, "backpack")
    except Exception as exc:  # pragma: no cover - import failure path
        raise CcxtUnavailable(
            "ccxt.async_support.backpack is not available. Install ccxt >= 4.0"
        ) from exc


def _load_ws_client() -> Callable[[], Any]:
    try:
        pro_module = _import_module("ccxt.pro")
        return getattr(pro_module, "backpack")
    except Exception as exc:  # pragma: no cover - import failure path
        raise CcxtUnavailable(
            "ccxt.pro.backpack is not available. Install ccxt.pro"
        ) from exc


class BackpackMetadataCache:
    """Lazy metadata cache backed by ccxt markets payload."""

    def __init__(self) -> None:
        self._lazy_client: Optional[Any] = None
        self._markets: Optional[Dict[str, Dict[str, Any]]] = None
        self._id_map: Dict[str, str] = {}

    async def ensure(self) -> None:
        if self._markets is not None:
            return
        client_ctor = _load_async_client()
        client = client_ctor()
        try:
            markets = await client.load_markets()
            self._markets = markets
            for symbol, meta in markets.items():
                normalized = symbol.replace("/", "-")
                self._id_map[normalized] = meta["id"]
        finally:
            await client.close()

    def id_for_symbol(self, symbol: str) -> str:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        try:
            return self._id_map[symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown symbol {symbol}") from exc

    def min_amount(self, symbol: str) -> Optional[Decimal]:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        meta = self._markets[self.symbol_to_ccxt(symbol)]
        limits = meta.get("limits", {}).get("amount", {})
        minimum = limits.get("min")
        return Decimal(str(minimum)) if minimum is not None else None

    def symbol_to_ccxt(self, symbol: str) -> str:
        return symbol.replace("-", "/")

    def ccxt_symbol_to_normalized(self, ccxt_symbol: str) -> str:
        return ccxt_symbol.replace("/", "-")


class BackpackRestTransport:
    """REST transport for order book snapshots."""

    def __init__(self, cache: BackpackMetadataCache) -> None:
        self._cache = cache
        self._client: Optional[Any] = None

    async def __aenter__(self) -> "BackpackRestTransport":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def _ensure_client(self) -> Any:
        if self._client is None:
            ctor = _load_async_client()
            self._client = ctor()
        return self._client

    async def order_book(self, symbol: str, *, limit: int | None = None) -> OrderBookSnapshot:
        await self._cache.ensure()
        client = await self._ensure_client()
        ccxt_symbol = self._cache.id_for_symbol(symbol)
        book = await client.fetch_order_book(ccxt_symbol, limit=limit)
        timestamp_raw = book.get("timestamp") or book.get("datetime")
        timestamp = None
        if timestamp_raw is not None:
            timestamp = float(timestamp_raw) / 1000.0
        return OrderBookSnapshot(
            symbol=symbol,
            bids=[(Decimal(str(price)), Decimal(str(amount))) for price, amount in book["bids"]],
            asks=[(Decimal(str(price)), Decimal(str(amount))) for price, amount in book["asks"]],
            timestamp=timestamp,
            sequence=book.get("nonce"),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


class BackpackWsTransport:
    """WebSocket transport built on ccxt.pro."""

    def __init__(self, cache: BackpackMetadataCache) -> None:
        self._cache = cache
        self._client: Optional[Any] = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            ctor = _load_ws_client()
            self._client = ctor()
        return self._client

    async def next_trade(self, symbol: str) -> TradeUpdate:
        await self._cache.ensure()
        client = self._ensure_client()
        ccxt_symbol = self._cache.id_for_symbol(symbol)
        trades = await client.watch_trades(ccxt_symbol)
        if not trades:
            raise asyncio.TimeoutError("No trades received")
        raw = trades[-1]
        price = Decimal(str(raw.get("p")))
        amount = Decimal(str(raw.get("q")))
        ts_raw = raw.get("ts") or raw.get("timestamp") or 0
        return TradeUpdate(
            symbol=symbol,
            price=price,
            amount=amount,
            side=raw.get("side"),
            trade_id=str(raw.get("t")),
            timestamp=float(ts_raw) / 1_000.0,
            sequence=raw.get("s"),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


__all__ = [
    "CcxtUnavailable",
    "BackpackMetadataCache",
    "BackpackRestTransport",
    "BackpackWsTransport",
    "OrderBookSnapshot",
    "TradeUpdate",
]
