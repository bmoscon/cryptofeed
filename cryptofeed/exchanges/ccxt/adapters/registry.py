"""Adapter registry and global access helpers."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Type

from .base import AdapterValidationError, BaseOrderBookAdapter, BaseTradeAdapter
from .hooks import AdapterHookRegistry
from .orderbook import CcxtOrderBookAdapter, FallbackOrderBookAdapter
from .trade import CcxtTradeAdapter, FallbackTradeAdapter


LOG = logging.getLogger("feedhandler")


class AdapterRegistry:
    """Registry managing exchange-specific adapters with sensible fallbacks."""

    def __init__(self) -> None:
        self._trade_adapters: Dict[str, Type[BaseTradeAdapter]] = {}
        self._orderbook_adapters: Dict[str, Type[BaseOrderBookAdapter]] = {}
        self._fallback_trade_cls: Type[BaseTradeAdapter] = FallbackTradeAdapter
        self._fallback_orderbook_cls: Type[BaseOrderBookAdapter] = FallbackOrderBookAdapter
        self._register_defaults()

    def _register_defaults(self) -> None:
        self._trade_adapters["default"] = CcxtTradeAdapter
        self._orderbook_adapters["default"] = CcxtOrderBookAdapter

    def reset(self) -> None:
        """Reset registry and hook state to defaults."""

        self._trade_adapters.clear()
        self._orderbook_adapters.clear()
        AdapterHookRegistry.reset()
        self._register_defaults()

    def register_trade_adapter(self, exchange_id: str, adapter_class: Type[BaseTradeAdapter]) -> None:
        if not issubclass(adapter_class, BaseTradeAdapter):
            raise AdapterValidationError(
                f"Adapter must inherit from BaseTradeAdapter: {adapter_class}"
            )
        self._trade_adapters[exchange_id] = adapter_class
        LOG.info("Registered trade adapter for %s: %s", exchange_id, adapter_class.__name__)

    def register_orderbook_adapter(self, exchange_id: str, adapter_class: Type[BaseOrderBookAdapter]) -> None:
        if not issubclass(adapter_class, BaseOrderBookAdapter):
            raise AdapterValidationError(
                f"Adapter must inherit from BaseOrderBookAdapter: {adapter_class}"
            )
        self._orderbook_adapters[exchange_id] = adapter_class
        LOG.info("Registered order book adapter for %s: %s", exchange_id, adapter_class.__name__)

    def register_trade_hook(self, exchange_id: str, hook: Callable) -> None:
        AdapterHookRegistry.register_trade_hook(exchange_id, hook)

    def register_orderbook_hook(self, exchange_id: str, hook: Callable) -> None:
        AdapterHookRegistry.register_orderbook_hook(exchange_id, hook)

    def register_trade_normalizer(self, exchange_id: str, field: str, func: Callable) -> None:
        AdapterHookRegistry.register_trade_normalizer(exchange_id, field, func)

    def register_orderbook_normalizer(self, exchange_id: str, field: str, func: Callable) -> None:
        AdapterHookRegistry.register_orderbook_normalizer(exchange_id, field, func)

    def get_trade_adapter(self, exchange_id: str) -> BaseTradeAdapter:
        adapter_class = self._trade_adapters.get(exchange_id, self._trade_adapters["default"])
        return adapter_class(exchange=exchange_id)

    def get_orderbook_adapter(self, exchange_id: str) -> BaseOrderBookAdapter:
        adapter_class = self._orderbook_adapters.get(exchange_id, self._orderbook_adapters["default"])
        return adapter_class(exchange=exchange_id)

    def convert_trade(self, exchange_id: str, raw_trade: Dict[str, Any]) -> Optional[Any]:
        adapter = self.get_trade_adapter(exchange_id)
        result = adapter.convert_trade(raw_trade)
        if result is not None:
            return result
        fallback = self._fallback_trade_cls(exchange=exchange_id)
        return fallback.convert_trade(raw_trade)

    def convert_orderbook(
        self, exchange_id: str, raw_orderbook: Dict[str, Any]
    ) -> Optional[Any]:
        adapter = self.get_orderbook_adapter(exchange_id)
        result = adapter.convert_orderbook(raw_orderbook)
        if result is not None:
            return result
        fallback = self._fallback_orderbook_cls(exchange=exchange_id)
        return fallback.convert_orderbook(raw_orderbook)

    def list_registered_adapters(self) -> Dict[str, Dict[str, str]]:
        return {
            "trade_adapters": {k: v.__name__ for k, v in self._trade_adapters.items()},
            "orderbook_adapters": {k: v.__name__ for k, v in self._orderbook_adapters.items()},
            "fallbacks": {
                "trade": self._fallback_trade_cls.__name__,
                "orderbook": self._fallback_orderbook_cls.__name__,
            },
        }


_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Return the global adapter registry."""
    return _registry


__all__ = ["AdapterRegistry", "get_adapter_registry"]
