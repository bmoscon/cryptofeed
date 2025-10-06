"""Hyperliquid-specific overrides for the CCXT integration layer."""
from __future__ import annotations

from typing import Optional

from cryptofeed.exchanges.ccxt.adapters import AdapterHookRegistry

from . import register_symbol_normalizer


def _normalize_symbol(raw_symbol: str, meta: Optional[dict] = None) -> str:
    normalized = raw_symbol.replace('/', '-').replace(':', '-')
    if normalized.endswith('-PERP'):
        return normalized

    base = meta.get('base') if meta else None
    quote = meta.get('quote') if meta else None

    if base is None or quote is None:
        base_quote = raw_symbol.split(':')[0]
        if '/' in base_quote:
            base, quote = base_quote.split('/')
        else:
            parts = normalized.split('-')
            base = parts[0]
            quote = parts[1] if len(parts) > 1 else parts[0]

    if quote and quote.endswith('USDT'):
        quote = 'USDT'

    return f"{base}-{quote}-PERP"


def _adapter_symbol_normalizer(normalized: str, raw_symbol: str, payload):
    return _normalize_symbol(raw_symbol)


def _register_hooks() -> None:
    AdapterHookRegistry.register_trade_normalizer(
        'hyperliquid', 'symbol', _adapter_symbol_normalizer
    )
    AdapterHookRegistry.register_orderbook_normalizer(
        'hyperliquid', 'symbol', _adapter_symbol_normalizer
    )


register_symbol_normalizer('hyperliquid', _normalize_symbol)
AdapterHookRegistry.register_reset_callback(_register_hooks)
_register_hooks()


__all__ = []

