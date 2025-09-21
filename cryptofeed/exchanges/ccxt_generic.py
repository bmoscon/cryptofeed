"""Generic ccxt/ccxt.pro integration scaffolding."""
from __future__ import annotations

import asyncio
import inspect
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
    """Raised when the required ccxt module cannot be imported."""


def _dynamic_import(path: str) -> Any:
    module = __import__(path.split('.')[0])
    for chunk in path.split('.')[1:]:
        module = getattr(module, chunk)
    return module


class CcxtMetadataCache:
    """Lazy metadata cache parameterised by ccxt exchange id."""

    def __init__(
        self,
        exchange_id: str,
        *,
        use_market_id: bool = False,
    ) -> None:
        self.exchange_id = exchange_id
        self.use_market_id = use_market_id
        self._markets: Optional[Dict[str, Dict[str, Any]]] = None
        self._id_map: Dict[str, str] = {}

    async def ensure(self) -> None:
        if self._markets is not None:
            return
        try:
            async_support = _dynamic_import("ccxt.async_support")
            ctor = getattr(async_support, self.exchange_id)
        except Exception as exc:  # pragma: no cover - import failure path
            raise CcxtUnavailable(
                f"ccxt.async_support.{self.exchange_id} unavailable"
            ) from exc
        client = ctor()
        try:
            markets = await client.load_markets()
            self._markets = markets
            for symbol, meta in markets.items():
                normalized = symbol.replace("/", "-")
                self._id_map[normalized] = meta.get("id", symbol)
        finally:
            await client.close()

    def id_for_symbol(self, symbol: str) -> str:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        try:
            return self._id_map[symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown symbol {symbol}") from exc

    def ccxt_symbol(self, symbol: str) -> str:
        return symbol.replace("-", "/")

    def request_symbol(self, symbol: str) -> str:
        if self.use_market_id:
            return self.id_for_symbol(symbol)
        return self.ccxt_symbol(symbol)

    def min_amount(self, symbol: str) -> Optional[Decimal]:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        market = self._markets[self.ccxt_symbol(symbol)]
        limits = market.get("limits", {}).get("amount", {})
        minimum = limits.get("min")
        return Decimal(str(minimum)) if minimum is not None else None


class CcxtRestTransport:
    """REST transport for order book snapshots."""

    def __init__(self, cache: CcxtMetadataCache) -> None:
        self._cache = cache
        self._client: Optional[Any] = None

    async def __aenter__(self) -> "CcxtRestTransport":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                async_support = _dynamic_import("ccxt.async_support")
                ctor = getattr(async_support, self._cache.exchange_id)
            except Exception as exc:  # pragma: no cover
                raise CcxtUnavailable(
                    f"ccxt.async_support.{self._cache.exchange_id} unavailable"
                ) from exc
            self._client = ctor()
        return self._client

    async def order_book(self, symbol: str, *, limit: Optional[int] = None) -> OrderBookSnapshot:
        await self._cache.ensure()
        client = await self._ensure_client()
        request_symbol = self._cache.request_symbol(symbol)
        book = await client.fetch_order_book(request_symbol, limit=limit)
        timestamp_raw = book.get("timestamp") or book.get("datetime")
        timestamp = float(timestamp_raw) / 1000.0 if timestamp_raw else None
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


class CcxtWsTransport:
    """WebSocket transport backed by ccxt.pro."""

    def __init__(self, cache: CcxtMetadataCache) -> None:
        self._cache = cache
        self._client: Optional[Any] = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                pro_module = _dynamic_import("ccxt.pro")
                ctor = getattr(pro_module, self._cache.exchange_id)
            except Exception as exc:  # pragma: no cover
                raise CcxtUnavailable(
                    f"ccxt.pro.{self._cache.exchange_id} unavailable"
                ) from exc
            self._client = ctor()
        return self._client

    async def next_trade(self, symbol: str) -> TradeUpdate:
        await self._cache.ensure()
        client = self._ensure_client()
        request_symbol = self._cache.request_symbol(symbol)
        trades = await client.watch_trades(request_symbol)
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
            timestamp=float(ts_raw) / 1_000_000.0,
            sequence=raw.get("s"),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


class CcxtGenericFeed:
    """Co-ordinates ccxt transports and dispatches normalized events."""

    def __init__(
        self,
        *,
        exchange_id: str,
        symbols: List[str],
        channels: List[str],
        snapshot_interval: int = 30,
        websocket_enabled: bool = True,
        rest_only: bool = False,
        metadata_cache: Optional[CcxtMetadataCache] = None,
        rest_transport_factory: Callable[[CcxtMetadataCache], CcxtRestTransport] = CcxtRestTransport,
        ws_transport_factory: Callable[[CcxtMetadataCache], CcxtWsTransport] = CcxtWsTransport,
    ) -> None:
        self.exchange_id = exchange_id
        self.symbols = symbols
        self.channels = set(channels)
        self.snapshot_interval = snapshot_interval
        self.websocket_enabled = websocket_enabled
        self.rest_only = rest_only
        self.cache = metadata_cache or CcxtMetadataCache(exchange_id)
        self.rest_factory = rest_transport_factory
        self.ws_factory = ws_transport_factory
        self._ws_transport: Optional[CcxtWsTransport] = None
        self._callbacks: Dict[str, List[Callable[[Any], Any]]] = {}

    def register_callback(self, channel: str, callback: Callable[[Any], Any]) -> None:
        self._callbacks.setdefault(channel, []).append(callback)

    async def bootstrap_l2(self, limit: Optional[int] = None) -> None:
        from cryptofeed.defines import L2_BOOK

        if L2_BOOK not in self.channels:
            return
        await self.cache.ensure()
        async with self.rest_factory(self.cache) as rest:
            for symbol in self.symbols:
                snapshot = await rest.order_book(symbol, limit=limit)
                await self._dispatch(L2_BOOK, snapshot)

    async def stream_trades_once(self) -> None:
        from cryptofeed.defines import TRADES

        if TRADES not in self.channels or self.rest_only or not self.websocket_enabled:
            return
        await self.cache.ensure()
        if self._ws_transport is None:
            self._ws_transport = self.ws_factory(self.cache)
        for symbol in self.symbols:
            update = await self._ws_transport.next_trade(symbol)
            await self._dispatch(TRADES, update)

    async def close(self) -> None:
        if self._ws_transport is not None:
            await self._ws_transport.close()
            self._ws_transport = None

    async def _dispatch(self, channel: str, payload: Any) -> None:
        callbacks = self._callbacks.get(channel, [])
        for cb in callbacks:
            result = cb(payload)
            if inspect.isawaitable(result):
                await result


__all__ = [
    "CcxtUnavailable",
    "CcxtMetadataCache",
    "CcxtRestTransport",
    "CcxtWsTransport",
    "CcxtGenericFeed",
    "OrderBookSnapshot",
    "TradeUpdate",
]
