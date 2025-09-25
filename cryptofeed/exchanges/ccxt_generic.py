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


# =============================================================================
# CCXT Exchange Builder Factory (Task 4.1)
# =============================================================================

import importlib
from typing import Type, Union, Set
from cryptofeed.feed import Feed
from cryptofeed.exchanges.ccxt_feed import CcxtFeed
from cryptofeed.exchanges.ccxt_config import CcxtExchangeConfig
from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter, BaseOrderBookAdapter


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


class CcxtExchangeBuilder:
    """Factory for creating CCXT-based feed classes."""

    def __init__(self):
        self._supported_exchanges: Optional[Set[str]] = None

    def _get_supported_exchanges(self) -> Set[str]:
        """Lazy load supported exchanges list."""
        if self._supported_exchanges is None:
            self._supported_exchanges = set(get_supported_ccxt_exchanges())
        return self._supported_exchanges

    def validate_exchange_id(self, exchange_id: str) -> bool:
        """Validate that exchange ID is supported by CCXT."""
        supported = self._get_supported_exchanges()
        return exchange_id in supported

    def normalize_exchange_id(self, exchange_id: str) -> str:
        """Normalize exchange ID to CCXT format."""
        # Convert to lowercase and handle common variations
        normalized = exchange_id.lower()

        # Handle common name variations
        mappings = {
            'coinbase-pro': 'coinbasepro',
            'huobi_pro': 'huobipro',
            'huobi-pro': 'huobipro',
            'binance_us': 'binanceus',
            'binance-us': 'binanceus'
        }

        return mappings.get(normalized, normalized.replace('-', '').replace('_', ''))

    def load_ccxt_async_module(self, exchange_id: str) -> Any:
        """Load CCXT async module for exchange."""
        try:
            import ccxt.async_support as ccxt_async
            if hasattr(ccxt_async, exchange_id):
                return getattr(ccxt_async, exchange_id)
            return None
        except (ImportError, AttributeError):
            return None

    def load_ccxt_pro_module(self, exchange_id: str) -> Any:
        """Load CCXT Pro module for exchange."""
        try:
            import ccxt.pro as ccxt_pro
            if hasattr(ccxt_pro, exchange_id):
                return getattr(ccxt_pro, exchange_id)
            return None
        except (ImportError, AttributeError):
            return None

    def get_exchange_features(self, exchange_id: str) -> List[str]:
        """Get supported features for exchange."""
        features = ['trades', 'orderbook']  # Basic features

        # Check if Pro WebSocket is available
        if self.load_ccxt_pro_module(exchange_id) is not None:
            features.append('websocket')

        return features

    def create_feed_class(
        self,
        exchange_id: str,
        *,
        symbol_normalizer: Optional[Callable[[str], str]] = None,
        subscription_filter: Optional[Callable[[str, str], bool]] = None,
        endpoint_overrides: Optional[Dict[str, str]] = None,
        config: Optional[CcxtExchangeConfig] = None,
        trade_adapter_class: Optional[Type[BaseTradeAdapter]] = None,
        orderbook_adapter_class: Optional[Type[BaseOrderBookAdapter]] = None
    ) -> Type[Feed]:
        """
        Create a feed class for the specified CCXT exchange.

        Args:
            exchange_id: CCXT exchange identifier
            symbol_normalizer: Custom symbol normalization function
            subscription_filter: Filter function for subscriptions
            endpoint_overrides: Custom endpoint URLs
            config: Exchange configuration
            trade_adapter_class: Custom trade adapter
            orderbook_adapter_class: Custom order book adapter

        Returns:
            Generated feed class inheriting from CcxtFeed

        Raises:
            UnsupportedExchangeError: If exchange is not supported
        """
        # Normalize and validate exchange ID
        normalized_id = self.normalize_exchange_id(exchange_id)

        if not self.validate_exchange_id(normalized_id):
            raise UnsupportedExchangeError(f"Exchange '{exchange_id}' is not supported by CCXT")

        # Create class name
        class_name = f"{exchange_id.title().replace('-', '').replace('_', '')}CcxtFeed"

        # Create dynamic class
        class_dict = {
            'exchange': normalized_id,
            'id': normalized_id.upper(),
            '_original_exchange_id': exchange_id,
            '_symbol_normalizer': symbol_normalizer,
            '_subscription_filter': subscription_filter,
            '_endpoint_overrides': endpoint_overrides or {},
            '_config': config,
        }

        # Add custom normalizer if provided, or default behavior
        if symbol_normalizer:
            # Capture the function in closure to avoid binding issues
            normalizer_func = symbol_normalizer
            def normalize_symbol(self, symbol: str) -> str:
                return normalizer_func(symbol)
            class_dict['normalize_symbol'] = normalize_symbol
        else:
            # Default symbol normalization (CCXT style to cryptofeed style)
            def normalize_symbol(self, symbol: str) -> str:
                return symbol.replace('/', '-')
            class_dict['normalize_symbol'] = normalize_symbol

        # Add subscription filter if provided
        if subscription_filter:
            # Capture the function in closure to avoid binding issues
            filter_func = subscription_filter
            def should_subscribe(self, symbol: str, channel: str) -> bool:
                return filter_func(symbol, channel)
            class_dict['should_subscribe'] = should_subscribe

        # Add endpoint overrides
        if endpoint_overrides:
            if 'rest' in endpoint_overrides:
                class_dict['rest_endpoint'] = endpoint_overrides['rest']
            if 'websocket' in endpoint_overrides:
                class_dict['ws_endpoint'] = endpoint_overrides['websocket']

        # Add custom adapters
        if trade_adapter_class:
            class_dict['trade_adapter_class'] = trade_adapter_class

            def _get_trade_adapter(self):
                return self.trade_adapter_class(exchange=self.exchange)
            class_dict['trade_adapter'] = property(_get_trade_adapter)

        if orderbook_adapter_class:
            class_dict['orderbook_adapter_class'] = orderbook_adapter_class

            def _get_orderbook_adapter(self):
                return self.orderbook_adapter_class(exchange=self.exchange)
            class_dict['orderbook_adapter'] = property(_get_orderbook_adapter)

        # Add configuration
        def __init__(self, *args, **kwargs):
            # Use provided config or create from exchange_id
            if self._config:
                kwargs['config'] = self._config
                # Set config as instance attribute for tests
                self.config = self._config
            else:
                kwargs['exchange_id'] = normalized_id

            super(generated_class, self).__init__(*args, **kwargs)

        class_dict['__init__'] = __init__

        # Create the class dynamically
        generated_class = type(class_name, (CcxtFeed,), class_dict)

        logger.info(f"Generated CCXT feed class: {class_name} for exchange: {normalized_id}")

        return generated_class


# Global builder instance
_exchange_builder = CcxtExchangeBuilder()


def get_exchange_builder() -> CcxtExchangeBuilder:
    """Get the global exchange builder instance."""
    return _exchange_builder


def create_ccxt_feed(exchange_id: str, **kwargs) -> Type[Feed]:
    """Convenience function to create CCXT feed class."""
    return _exchange_builder.create_feed_class(exchange_id, **kwargs)


__all__ = [
    "CcxtUnavailable",
    "CcxtMetadataCache",
    "CcxtRestTransport",
    "CcxtWsTransport",
    "CcxtGenericFeed",
    "OrderBookSnapshot",
    "TradeUpdate",
    "CcxtExchangeBuilder",
    "UnsupportedExchangeError",
    "get_supported_ccxt_exchanges",
    "get_exchange_builder",
    "create_ccxt_feed",
]
