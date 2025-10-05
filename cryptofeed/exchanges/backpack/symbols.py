from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Optional

from cryptofeed.exchanges.native.symbols import NativeMarket, NativeSymbolService

@dataclass(frozen=True, slots=True)
class BackpackMarket(NativeMarket):
    """Normalized Backpack market metadata."""

    instrument_type: str = "SPOT"
    price_precision: Optional[int] = None
    amount_precision: Optional[int] = None
    min_amount: Optional[Decimal] = None


class BackpackSymbolService(NativeSymbolService):
    """Backpack-specific symbol loader built atop the native toolkit."""

    market_class = BackpackMarket

    def __init__(self, *, rest_client, ttl_seconds: int = 900) -> None:
        super().__init__(rest_client=rest_client, ttl_seconds=ttl_seconds)

    def _include_market(self, entry: Mapping[str, object]) -> bool:
        status = str(entry.get("status", "")).upper()
        return status in {"TRADING", "ENABLED", ""}

    def _normalize_symbol(self, native_symbol: str, entry: Mapping[str, object]) -> str:  # noqa: ARG002
        return native_symbol.replace("_", "-").replace("/", "-")

    def _instrument_type(self, entry: Mapping[str, object]) -> Optional[str]:
        market_type = str(entry.get("type", "spot")).upper()
        if market_type == "PERPETUAL":
            return "PERPETUAL"
        if market_type in {"FUTURE", "FUTURES"}:
            return "FUTURES"
        return "SPOT"

    def _build_market(
        self,
        entry: Mapping[str, object],
        normalized_symbol: str,
        native_symbol: str,
    ) -> BackpackMarket:
        precision = entry.get("precision", {}) if isinstance(entry, Mapping) else {}
        limits = entry.get("limits", {}) if isinstance(entry, Mapping) else {}
        amount_limits = limits.get("amount", {}) if isinstance(limits, Mapping) else {}
        min_amount_raw = amount_limits.get("min") if isinstance(amount_limits, Mapping) else None
        min_amount = Decimal(str(min_amount_raw)) if min_amount_raw is not None else None

        return BackpackMarket(
            normalized_symbol=normalized_symbol,
            native_symbol=native_symbol,
            instrument_type=self._instrument_type(entry) or "SPOT",
            price_precision=precision.get("price") if isinstance(precision, Mapping) else None,
            amount_precision=precision.get("amount") if isinstance(precision, Mapping) else None,
            min_amount=min_amount,
            metadata=entry,
        )
