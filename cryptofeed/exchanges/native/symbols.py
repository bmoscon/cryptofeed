"""Reusable symbol metadata services for native exchanges."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


@dataclass(frozen=True, slots=True)
class NativeMarket:
    """Canonical representation of a native exchange market."""

    normalized_symbol: str
    native_symbol: str
    instrument_type: Optional[str] = None
    metadata: Optional[Mapping[str, Any]] = None


class NativeSymbolService:
    """Base class providing caching and normalization for native exchanges."""

    market_class = NativeMarket

    def __init__(self, *, rest_client: Any, ttl_seconds: int = 900) -> None:
        self._rest_client = rest_client
        self._ttl = max(ttl_seconds, 0)
        self._lock = asyncio.Lock()
        self._markets: Dict[str, NativeMarket] = {}
        self._native_to_normalized: Dict[str, str] = {}
        self._expires_at: Optional[datetime] = None

    async def ensure(self, *, force: bool = False) -> None:
        """Ensure market metadata is loaded, respecting TTL and force reload."""

        async with self._lock:
            now = datetime.now(timezone.utc)
            if not force and self._expires_at and self._expires_at > now and self._markets:
                return

            raw_markets = await self._fetch_markets()
            markets, native_map = self._parse_markets(raw_markets)
            self._markets = markets
            self._native_to_normalized = native_map
            self._expires_at = (now + timedelta(seconds=self._ttl)) if self._ttl else None

    async def _fetch_markets(self) -> Iterable[Mapping[str, Any]]:
        fetch = getattr(self._rest_client, "fetch_markets", None)
        if not callable(fetch):  # pragma: no cover - configurable guard
            raise RuntimeError("rest_client must provide a fetch_markets coroutine")
        return await fetch()

    def _parse_markets(
        self,
        markets: Iterable[Mapping[str, Any]],
    ) -> Tuple[Dict[str, NativeMarket], Dict[str, str]]:
        parsed: Dict[str, NativeMarket] = {}
        native_map: Dict[str, str] = {}

        for entry in markets:
            if not isinstance(entry, Mapping):  # pragma: no cover - defensive guard
                continue
            if not self._include_market(entry):
                continue

            native_symbol = self._extract_native_symbol(entry)
            normalized_symbol = self._normalize_symbol(native_symbol, entry)
            market = self._build_market(entry, normalized_symbol, native_symbol)
            parsed[normalized_symbol] = market
            native_map[native_symbol] = normalized_symbol

        return parsed, native_map

    def _include_market(self, entry: Mapping[str, Any]) -> bool:
        return True

    def _extract_native_symbol(self, entry: Mapping[str, Any]) -> str:
        symbol = entry.get("symbol")
        if not symbol:
            raise KeyError("Market entry missing 'symbol'")
        return str(symbol)

    def _normalize_symbol(self, native_symbol: str, entry: Mapping[str, Any]) -> str:  # noqa: ARG002
        return native_symbol

    def _instrument_type(self, entry: Mapping[str, Any]) -> Optional[str]:
        instrument = entry.get("type")
        return str(instrument).upper() if instrument else None

    def _metadata(self, entry: Mapping[str, Any]) -> Optional[Mapping[str, Any]]:
        return entry

    def _build_market(
        self,
        entry: Mapping[str, Any],
        normalized_symbol: str,
        native_symbol: str,
    ) -> NativeMarket:
        instrument_type = self._instrument_type(entry)
        metadata = self._metadata(entry)
        return self.market_class(
            normalized_symbol=normalized_symbol,
            native_symbol=native_symbol,
            instrument_type=instrument_type,
            metadata=metadata,
        )

    def get_market(self, symbol: str) -> NativeMarket:
        try:
            return self._markets[symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown symbol: {symbol}") from exc

    def native_symbol(self, symbol: str) -> str:
        return self.get_market(symbol).native_symbol

    def normalized_symbol(self, native_symbol: str) -> str:
        try:
            return self._native_to_normalized[native_symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown native symbol: {native_symbol}") from exc

    def all_markets(self) -> Iterable[NativeMarket]:
        return self._markets.values()

    def clear(self) -> None:
        self._markets = {}
        self._native_to_normalized = {}
        self._expires_at = None


__all__ = ["NativeMarket", "NativeSymbolService"]
