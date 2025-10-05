"""CCXT adapter package exposing base, concrete, and fallback adapters."""
from .base import AdapterValidationError, BaseOrderBookAdapter, BaseTradeAdapter
from .hooks import AdapterHookRegistry, ccxt_orderbook_hook, ccxt_trade_hook
from .orderbook import CcxtOrderBookAdapter, FallbackOrderBookAdapter
from .registry import AdapterRegistry, get_adapter_registry
from .trade import CcxtTradeAdapter, FallbackTradeAdapter
from .type_adapter import CcxtTypeAdapter


def _hyperliquid_symbol_normalizer(normalized: str, raw_symbol: str, payload):
    base_quote = raw_symbol.split(":")[0]
    if "/" in base_quote:
        base, quote = base_quote.split("/")
    else:  # pragma: no cover - defensive guard
        parts = normalized.split("-")
        base = parts[0]
        quote = parts[1] if len(parts) > 1 else parts[0]
    return f"{base}-{quote}-PERP"


def _register_default_normalizers() -> None:
    AdapterHookRegistry.register_trade_normalizer(
        "hyperliquid", "symbol", _hyperliquid_symbol_normalizer
    )
    AdapterHookRegistry.register_orderbook_normalizer(
        "hyperliquid", "symbol", _hyperliquid_symbol_normalizer
    )


AdapterHookRegistry.register_reset_callback(_register_default_normalizers)
_register_default_normalizers()

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
