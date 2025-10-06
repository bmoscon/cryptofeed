"""CCXT adapter package exposing base, concrete, and fallback adapters."""
from .base import AdapterValidationError, BaseOrderBookAdapter, BaseTradeAdapter
from .hooks import AdapterHookRegistry, ccxt_orderbook_hook, ccxt_trade_hook
from .orderbook import CcxtOrderBookAdapter, FallbackOrderBookAdapter
from .registry import AdapterRegistry, get_adapter_registry
from .trade import CcxtTradeAdapter, FallbackTradeAdapter
from .type_adapter import CcxtTypeAdapter

__all__ = [
    "AdapterHookRegistry",
    "AdapterRegistry",
    "AdapterValidationError",
    "BaseOrderBookAdapter",
    "BaseTradeAdapter",
    "CcxtOrderBookAdapter",
    "CcxtTypeAdapter",
    "CcxtTradeAdapter",
    "ccxt_orderbook_hook",
    "ccxt_trade_hook",
    "FallbackOrderBookAdapter",
    "FallbackTradeAdapter",
    "get_adapter_registry",
]
