"""Exchange-specific overrides for CCXT integration."""
from __future__ import annotations

from typing import Callable, Dict, Optional

SymbolNormalizer = Callable[[str, Optional[dict]], str]

_SYMBOL_NORMALIZERS: Dict[str, SymbolNormalizer] = {}
_LOADED = False


def register_symbol_normalizer(exchange_id: str, normalizer: SymbolNormalizer) -> None:
    _SYMBOL_NORMALIZERS[exchange_id] = normalizer


def get_symbol_normalizer(exchange_id: str) -> Optional[SymbolNormalizer]:
    _ensure_loaded()
    return _SYMBOL_NORMALIZERS.get(exchange_id)


def load_exchange_overrides() -> None:
    _ensure_loaded()


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    # Import modules that register exchange-specific overrides.
    from . import hyperliquid  # noqa: F401  # pylint: disable=unused-import

    _LOADED = True


__all__ = [
    "SymbolNormalizer",
    "register_symbol_normalizer",
    "get_symbol_normalizer",
    "load_exchange_overrides",
]

