"""Generic ccxt/ccxt.pro integration scaffolding."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Iterable, Set
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
from .context import CcxtExchangeContext
from .exchanges import get_symbol_normalizer

if TYPE_CHECKING:  # pragma: no cover - import for type checking only
    from .transport import CcxtRestTransport, CcxtWsTransport


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
        self._symbol_map: Dict[str, str] = {}

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
        kwargs = self._client_kwargs()
        if not kwargs:
            client = ctor()
        else:
            try:
                client = ctor(**kwargs)
            except TypeError:
                client = ctor()
                try:
                    client.__dict__.setdefault('_cryptofeed_init_kwargs', {}).update(kwargs)
                except Exception:  # pragma: no cover - defensive fallback
                    pass
        try:
            markets = await client.load_markets()
            self._markets = markets
            for symbol, meta in markets.items():
                normalized = self._normalize_symbol(symbol, meta)
                self._id_map[normalized] = meta.get("id", symbol)
                self._symbol_map[normalized] = symbol
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
        if symbol in self._symbol_map:
            return self._symbol_map[symbol]
        return self.ccxt_symbol(symbol)

    def min_amount(self, symbol: str) -> Optional[Decimal]:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        ccxt_symbol = self._symbol_map.get(symbol, self.ccxt_symbol(symbol))
        market = self._markets[ccxt_symbol]
        limits = market.get("limits", {}).get("amount", {})
        minimum = limits.get("min")
        return Decimal(str(minimum)) if minimum is not None else None

    def market_metadata(self, symbol: str) -> Dict[str, Any]:
        if self._markets is None:
            raise RuntimeError("Metadata cache not initialised")
        ccxt_symbol = self._symbol_map.get(symbol, self.ccxt_symbol(symbol))
        try:
            return self._markets[ccxt_symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown symbol {symbol}") from exc

    def _normalize_symbol(self, symbol: str, meta: Dict[str, Any]) -> str:
        normalizer = get_symbol_normalizer(self.exchange_id)
        if normalizer is not None:
            return normalizer(symbol, meta)
        normalized = symbol.replace("/", "-")
        if ":" in normalized:
            normalized = normalized.replace(":", "-")
        return normalized


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
        rest_transport_factory: Optional[Callable[[CcxtMetadataCache], Any]] = None,
        ws_transport_factory: Optional[Callable[[CcxtMetadataCache], Any]] = None,
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
        if self._context:
            metadata_cache = metadata_cache or CcxtMetadataCache(
                exchange_id, context=self._context
            )
        self.cache = metadata_cache or CcxtMetadataCache(exchange_id)
        self._authentication_callbacks: List[Callable[[Any], Any]] = []
        self.rest_factory = rest_transport_factory or self._create_default_rest_factory()
        self.ws_factory = ws_transport_factory or self._create_default_ws_factory()
        self._ws_transport = None
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
        try:
            for symbol in self.symbols:
                update = await self._ws_transport.next_trade(symbol)
                await self._dispatch(TRADES, update)
        except CcxtUnavailable as exc:
            self.rest_only = True
            self.websocket_enabled = False
            if self._ws_transport is not None:
                await self._ws_transport.close()
                self._ws_transport = None
            logger.warning(
                "ccxt feed falling back to REST",
                exchange=self.exchange_id,
                reason=str(exc),
            )

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

    def _create_default_rest_factory(self) -> Callable[[CcxtMetadataCache], 'CcxtRestTransport']:
        def factory(cache: CcxtMetadataCache, **kwargs: Any) -> CcxtRestTransport:
            from .transport import CcxtRestTransport

            return CcxtRestTransport(cache, **kwargs)

        return factory

    def _create_default_ws_factory(self) -> Callable[[CcxtMetadataCache], 'CcxtWsTransport']:
        def factory(cache: CcxtMetadataCache, **kwargs: Any) -> CcxtWsTransport:
            from .transport import CcxtWsTransport

            return CcxtWsTransport(cache, **kwargs)

        return factory

__all__ = [
    "CcxtUnavailable",
    "CcxtMetadataCache",
    "CcxtGenericFeed",
    "OrderBookSnapshot",
    "TradeUpdate",
    "get_supported_ccxt_exchanges",
]


def get_supported_ccxt_exchanges() -> List[str]:
    """Return sorted list of exchanges supported by the installed ccxt package."""
    try:
        ccxt = _dynamic_import('ccxt')
        exchanges = list(getattr(ccxt, 'exchanges', []))
    except ImportError:
        logger.warning("CCXT not available - returning empty exchange list")
        return []
    return sorted(exchanges)
