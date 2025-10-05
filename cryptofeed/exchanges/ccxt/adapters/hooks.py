"""Hook registry utilities for CCXT adapters."""
from __future__ import annotations

import logging
from collections import defaultdict
from copy import deepcopy
from typing import Any, Callable, ClassVar, DefaultDict, Dict, Iterable, List, MutableMapping, Optional

LOG = logging.getLogger("feedhandler")

TradePayload = MutableMapping[str, Any]
OrderBookPayload = MutableMapping[str, Any]

TradeHook = Callable[[TradePayload], Optional[TradePayload]]
OrderBookHook = Callable[[OrderBookPayload], Optional[OrderBookPayload]]

TradeNormalizer = Callable[[Any, Any, TradePayload], Any]
OrderBookNormalizer = Callable[[Any, Any, OrderBookPayload], Any]


class AdapterHookRegistry:
    """Central registry for adapter payload and normalization hooks."""

    _trade_hooks: DefaultDict[str, List[TradeHook]] = defaultdict(list)
    _orderbook_hooks: DefaultDict[str, List[OrderBookHook]] = defaultdict(list)

    _trade_normalizers: DefaultDict[str, Dict[str, TradeNormalizer]] = defaultdict(dict)
    _orderbook_normalizers: DefaultDict[str, Dict[str, OrderBookNormalizer]] = defaultdict(dict)

    @classmethod
    def register_trade_hook(cls, exchange_id: str, hook: TradeHook) -> None:
        cls._trade_hooks[exchange_id].append(hook)

    @classmethod
    def register_orderbook_hook(cls, exchange_id: str, hook: OrderBookHook) -> None:
        cls._orderbook_hooks[exchange_id].append(hook)

    @classmethod
    def register_trade_normalizer(cls, exchange_id: str, field: str, func: TradeNormalizer) -> None:
        cls._trade_normalizers[exchange_id][field] = func

    @classmethod
    def register_orderbook_normalizer(cls, exchange_id: str, field: str, func: OrderBookNormalizer) -> None:
        cls._orderbook_normalizers[exchange_id][field] = func

    @classmethod
    def trade_payload_hooks(cls, exchange_id: str) -> Iterable[TradeHook]:
        yield from cls._trade_hooks.get("default", [])
        yield from cls._trade_hooks.get(exchange_id, [])

    @classmethod
    def orderbook_payload_hooks(cls, exchange_id: str) -> Iterable[OrderBookHook]:
        yield from cls._orderbook_hooks.get("default", [])
        yield from cls._orderbook_hooks.get(exchange_id, [])

    @classmethod
    def trade_normalizer(cls, exchange_id: str, field: str) -> Optional[TradeNormalizer]:
        normalizer = cls._trade_normalizers.get(exchange_id, {}).get(field)
        if normalizer:
            return normalizer
        return cls._trade_normalizers.get("default", {}).get(field)

    @classmethod
    def orderbook_normalizer(cls, exchange_id: str, field: str) -> Optional[OrderBookNormalizer]:
        normalizer = cls._orderbook_normalizers.get(exchange_id, {}).get(field)
        if normalizer:
            return normalizer
        return cls._orderbook_normalizers.get("default", {}).get(field)

    _reset_callbacks: ClassVar[List[Callable[[], None]]] = []

    @classmethod
    def reset(cls) -> None:
        cls._trade_hooks.clear()
        cls._orderbook_hooks.clear()
        cls._trade_normalizers.clear()
        cls._orderbook_normalizers.clear()
        for callback in cls._reset_callbacks:
            try:
                callback()
            except Exception as exc:  # pragma: no cover - defensive guard
                LOG.warning("R3 adapter reset callback failed: %s", exc)

    @classmethod
    def register_reset_callback(cls, callback: Callable[[], None]) -> None:
        cls._reset_callbacks.append(callback)


def ccxt_trade_hook(
    exchange_id: str,
    *,
    symbol: Optional[TradeNormalizer] = None,
    price: Optional[TradeNormalizer] = None,
    timestamp: Optional[TradeNormalizer] = None,
) -> Callable[[TradeHook], TradeHook]:
    """Decorator to register trade payload hooks and optional normalizers."""

    def decorator(func: TradeHook) -> TradeHook:
        AdapterHookRegistry.register_trade_hook(exchange_id, func)
        if symbol is not None:
            AdapterHookRegistry.register_trade_normalizer(exchange_id, "symbol", symbol)
        if price is not None:
            AdapterHookRegistry.register_trade_normalizer(exchange_id, "price", price)
        if timestamp is not None:
            AdapterHookRegistry.register_trade_normalizer(exchange_id, "timestamp", timestamp)
        return func

    return decorator


def ccxt_orderbook_hook(
    exchange_id: str,
    *,
    symbol: Optional[OrderBookNormalizer] = None,
    price_levels: Optional[OrderBookNormalizer] = None,
    timestamp: Optional[OrderBookNormalizer] = None,
) -> Callable[[OrderBookHook], OrderBookHook]:
    """Decorator to register order book payload hooks and optional normalizers."""

    def decorator(func: OrderBookHook) -> OrderBookHook:
        AdapterHookRegistry.register_orderbook_hook(exchange_id, func)
        if symbol is not None:
            AdapterHookRegistry.register_orderbook_normalizer(exchange_id, "symbol", symbol)
        if price_levels is not None:
            AdapterHookRegistry.register_orderbook_normalizer(exchange_id, "price_levels", price_levels)
        if timestamp is not None:
            AdapterHookRegistry.register_orderbook_normalizer(exchange_id, "timestamp", timestamp)
        return func

    return decorator


def apply_trade_hooks(exchange_id: str, payload: TradePayload) -> TradePayload:
    """Apply registered trade hooks and return the possibly modified payload."""

    working = deepcopy(payload)
    for hook in AdapterHookRegistry.trade_payload_hooks(exchange_id):
        try:
            result = hook(working)
            if result is None:
                continue
            if not isinstance(result, MutableMapping):
                LOG.warning(
                    "R3 trade hook for %s returned non-mapping %s", exchange_id, type(result)
                )
                continue
            working = result
        except Exception as exc:  # pragma: no cover - defensive guard
            LOG.warning(
                "R3 trade hook failure for %s: %s", exchange_id, exc
            )
    return working


def apply_orderbook_hooks(exchange_id: str, payload: OrderBookPayload) -> OrderBookPayload:
    """Apply registered order book hooks and return the possibly modified payload."""

    working = deepcopy(payload)
    for hook in AdapterHookRegistry.orderbook_payload_hooks(exchange_id):
        try:
            result = hook(working)
            if result is None:
                continue
            if not isinstance(result, MutableMapping):
                LOG.warning(
                    "R3 order book hook for %s returned non-mapping %s", exchange_id, type(result)
                )
                continue
            working = result
        except Exception as exc:  # pragma: no cover - defensive guard
            LOG.warning(
                "R3 order book hook failure for %s: %s", exchange_id, exc
            )
    return working


__all__ = [
    "AdapterHookRegistry",
    "apply_orderbook_hooks",
    "apply_trade_hooks",
    "ccxt_orderbook_hook",
    "ccxt_trade_hook",
    "register_reset_callback",
]
