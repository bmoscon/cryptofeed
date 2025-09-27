"""Generic ccxt/ccxt.pro integration scaffolding."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, Iterable, Set
import sys

from loguru import logger

from cryptofeed.defines import (
    BALANCES,
    FILLS,
    ORDERS,
    ORDER_INFO,
    ORDER_STATUS,
    POSITIONS,
    TRADE_HISTORY,
    TRANSACTIONS,
)
from .config import CcxtExchangeContext


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


def _resolve_dynamic_import() -> Callable[[str], Any]:
    shim = sys.modules.get('cryptofeed.exchanges.ccxt_generic')
    if shim is not None and hasattr(shim, '_dynamic_import'):
        return getattr(shim, '_dynamic_import')
    return _dynamic_import


AUTH_REQUIRED_CHANNELS: Set[str] = {
    BALANCES,
    FILLS,
    ORDERS,
    ORDER_INFO,
    ORDER_STATUS,
    POSITIONS,
    TRADE_HISTORY,
    TRANSACTIONS,
}


class CcxtMetadataCache:
    """Lazy metadata cache parameterised by ccxt exchange id."""

    def __init__(
        self,
        exchange_id: str,
        *,
        use_market_id: bool = False,
        context: Optional[CcxtExchangeContext] = None,
    ) -> None:
        self.exchange_id = exchange_id
        self._context = context
        self.use_market_id = (
            context.transport.use_market_id if context else use_market_id
        )
        self._markets: Optional[Dict[str, Dict[str, Any]]] = None
        self._id_map: Dict[str, str] = {}

    def _client_kwargs(self) -> Dict[str, Any]:
        if not self._context:
            return {}
        kwargs = dict(self._context.ccxt_options)
        proxy_url = self._context.http_proxy_url
        if proxy_url:
            kwargs.setdefault('aiohttp_proxy', proxy_url)
            kwargs.setdefault('proxies', {'http': proxy_url, 'https': proxy_url})
        kwargs.setdefault('enableRateLimit', kwargs.get('enableRateLimit', True))
        return kwargs

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
        client = ctor(self._client_kwargs())
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

    def __init__(
        self,
        cache: CcxtMetadataCache,
        *,
        context: Optional[CcxtExchangeContext] = None,
        require_auth: bool = False,
        auth_callbacks: Optional[Iterable[Callable[[Any], Any]]] = None,
    ) -> None:
        self._cache = cache
        self._client: Optional[Any] = None
        self._context = context
        self._require_auth = require_auth
        self._auth_callbacks = list(auth_callbacks or [])
        self._authenticated = False

    async def __aenter__(self) -> "CcxtRestTransport":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                async_support = _resolve_dynamic_import()("ccxt.async_support")
                ctor = getattr(async_support, self._cache.exchange_id)
            except Exception as exc:  # pragma: no cover
                raise CcxtUnavailable(
                    f"ccxt.async_support.{self._cache.exchange_id} unavailable"
                ) from exc
            self._client = ctor(self._client_kwargs())
        return self._client

    def _client_kwargs(self) -> Dict[str, Any]:
        if not self._context:
            return {}
        kwargs = dict(self._context.ccxt_options)
        proxy_url = self._context.http_proxy_url
        if proxy_url:
            kwargs.setdefault('aiohttp_proxy', proxy_url)
            kwargs.setdefault('proxies', {'http': proxy_url, 'https': proxy_url})
        kwargs.setdefault('enableRateLimit', kwargs.get('enableRateLimit', True))
        return kwargs

    async def _authenticate_client(self, client: Any) -> None:
        if not self._require_auth or self._authenticated:
            return
        checker = getattr(client, 'check_required_credentials', None)
        if checker is not None:
            try:
                checker()
            except Exception as exc:  # pragma: no cover - relies on ccxt error details
                raise RuntimeError(
                    "CCXT credentials are invalid or incomplete for REST transport"
                ) from exc
        for callback in self._auth_callbacks:
            result = callback(client)
            if inspect.isawaitable(result):
                await result
        self._authenticated = True

    async def order_book(self, symbol: str, *, limit: Optional[int] = None) -> OrderBookSnapshot:
        await self._cache.ensure()
        client = await self._ensure_client()
        await self._authenticate_client(client)
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

    def __init__(
        self,
        cache: CcxtMetadataCache,
        *,
        context: Optional[CcxtExchangeContext] = None,
        require_auth: bool = False,
        auth_callbacks: Optional[Iterable[Callable[[Any], Any]]] = None,
    ) -> None:
        self._cache = cache
        self._client: Optional[Any] = None
        self._context = context
        self._require_auth = require_auth
        self._auth_callbacks = list(auth_callbacks or [])
        self._authenticated = False

    def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                pro_module = _resolve_dynamic_import()("ccxt.pro")
                ctor = getattr(pro_module, self._cache.exchange_id)
            except Exception as exc:  # pragma: no cover
                raise CcxtUnavailable(
                    f"ccxt.pro.{self._cache.exchange_id} unavailable"
                ) from exc
            self._client = ctor(self._client_kwargs())
        return self._client

    def _client_kwargs(self) -> Dict[str, Any]:
        if not self._context:
            return {}
        kwargs = dict(self._context.ccxt_options)
        proxy_url = self._context.websocket_proxy_url or self._context.http_proxy_url
        if proxy_url:
            kwargs.setdefault('aiohttp_proxy', proxy_url)
            kwargs.setdefault('proxies', {'http': proxy_url, 'https': proxy_url})
        kwargs.setdefault('enableRateLimit', kwargs.get('enableRateLimit', True))
        return kwargs

    async def _authenticate_client(self, client: Any) -> None:
        if not self._require_auth or self._authenticated:
            return
        checker = getattr(client, 'check_required_credentials', None)
        if checker is not None:
            try:
                checker()
            except Exception as exc:  # pragma: no cover
                raise RuntimeError(
                    "CCXT credentials are invalid or incomplete for WebSocket transport"
                ) from exc
        for callback in self._auth_callbacks:
            result = callback(client)
            if inspect.isawaitable(result):
                await result
        self._authenticated = True

    async def next_trade(self, symbol: str) -> TradeUpdate:
        await self._cache.ensure()
        client = self._ensure_client()
        await self._authenticate_client(client)
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
        config_context: Optional[CcxtExchangeContext] = None,
    ) -> None:
        self.exchange_id = exchange_id
        self.symbols = symbols
        self.channels = set(channels)
        self._context = config_context

        if self._context:
            snapshot_interval = self._context.transport.snapshot_interval
            websocket_enabled = self._context.transport.websocket_enabled
            rest_only = self._context.transport.rest_only

        self.snapshot_interval = snapshot_interval
        self.websocket_enabled = websocket_enabled
        self.rest_only = rest_only
        self._authentication_callbacks: List[Callable[[Any], Any]] = []
        if self._context:
            metadata_cache = metadata_cache or CcxtMetadataCache(
                exchange_id, context=self._context
            )
        self.cache = metadata_cache or CcxtMetadataCache(exchange_id)
        self.rest_factory = rest_transport_factory
        self.ws_factory = ws_transport_factory
        self._ws_transport: Optional[CcxtWsTransport] = None
        self._callbacks: Dict[str, List[Callable[[Any], Any]]] = {}
        self._auth_channels = self.channels.intersection(AUTH_REQUIRED_CHANNELS)
        self._requires_authentication = bool(self._auth_channels)

        if self._requires_authentication:
            if not self._context:
                raise RuntimeError(
                    "CCXT private channels requested but no configuration context provided"
                )
            credentials_ok = bool(
                self._context.ccxt_options.get('apiKey')
                and self._context.ccxt_options.get('secret')
            )
            if not credentials_ok:
                raise RuntimeError(
                    "CCXT private channels requested but required credentials are missing"
                )

    def register_callback(self, channel: str, callback: Callable[[Any], Any]) -> None:
        self._callbacks.setdefault(channel, []).append(callback)

    def register_authentication_callback(self, callback: Callable[[Any], Any]) -> None:
        self._authentication_callbacks.append(callback)

    async def bootstrap_l2(self, limit: Optional[int] = None) -> None:
        from cryptofeed.defines import L2_BOOK

        if L2_BOOK not in self.channels:
            return
        await self.cache.ensure()
        async with self._create_rest_transport() as rest:
            for symbol in self.symbols:
                snapshot = await rest.order_book(symbol, limit=limit)
                await self._dispatch(L2_BOOK, snapshot)

    async def stream_trades_once(self) -> None:
        from cryptofeed.defines import TRADES

        if TRADES not in self.channels or self.rest_only or not self.websocket_enabled:
            return
        await self.cache.ensure()
        if self._ws_transport is None:
            self._ws_transport = self._create_ws_transport()
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

    def _rest_transport_kwargs(self) -> Dict[str, Any]:
        return {
            'context': self._context,
            'require_auth': self._requires_authentication,
            'auth_callbacks': list(self._authentication_callbacks),
        }

    def _ws_transport_kwargs(self) -> Dict[str, Any]:
        return {
            'context': self._context,
            'require_auth': self._requires_authentication,
            'auth_callbacks': list(self._authentication_callbacks),
        }

    def _create_rest_transport(self) -> CcxtRestTransport:
        return self.rest_factory(self.cache, **self._rest_transport_kwargs())

    def _create_ws_transport(self) -> CcxtWsTransport:
        return self.ws_factory(self.cache, **self._ws_transport_kwargs())


# =============================================================================
# CCXT Exchange Builder Factory (Task 4.1)
# =============================================================================

import importlib
from typing import Type, Union, Set
from cryptofeed.feed import Feed
from .feed import CcxtFeed
from .config import CcxtExchangeConfig
from .adapters import BaseTradeAdapter, BaseOrderBookAdapter


class UnsupportedExchangeError(Exception):
    """Raised when an unsupported exchange is requested."""
    pass


def get_supported_ccxt_exchanges() -> List[str]:
    """Get list of supported CCXT exchanges."""
    try:
        ccxt = _dynamic_import('ccxt')
        exchanges = list(ccxt.exchanges)
        return sorted(exchanges)
    except ImportError:
        logger.warning("CCXT not available - returning empty exchange list")
        return []


__all__ = [
    "CcxtUnavailable",
    "CcxtMetadataCache",
    "CcxtRestTransport",
    "CcxtWsTransport",
    "CcxtGenericFeed",
    "OrderBookSnapshot",
    "TradeUpdate",
]
