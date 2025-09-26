from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Iterable, Optional


@dataclass(frozen=True, slots=True)
class BackpackMarket:
    """Normalized Backpack market metadata."""

    normalized_symbol: str
    native_symbol: str
    instrument_type: str
    price_precision: Optional[int]
    amount_precision: Optional[int]
    min_amount: Optional[Decimal]


class BackpackSymbolService:
    """Loads and caches Backpack market metadata for symbol normalization."""

    def __init__(self, *, rest_client, ttl_seconds: int = 900):
        self._rest_client = rest_client
        self._ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()
        self._markets: Dict[str, BackpackMarket] = {}
        self._expires_at: Optional[datetime] = None

    async def ensure(self, *, force: bool = False) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if not force and self._expires_at and now < self._expires_at and self._markets:
                return

            raw_markets = await self._rest_client.fetch_markets()
            self._markets = self._parse_markets(raw_markets)
            self._expires_at = now + self._ttl

    def get_market(self, symbol: str) -> BackpackMarket:
        try:
            return self._markets[symbol]
        except KeyError as exc:
            raise KeyError(f"Unknown Backpack symbol: {symbol}") from exc

    def native_symbol(self, symbol: str) -> str:
        return self.get_market(symbol).native_symbol

    def all_markets(self) -> Iterable[BackpackMarket]:
        return self._markets.values()

    def clear(self) -> None:
        self._markets = {}
        self._expires_at = None

    @staticmethod
    def _parse_markets(markets: Iterable[dict]) -> Dict[str, BackpackMarket]:
        parsed: Dict[str, BackpackMarket] = {}
        for entry in markets:
            if entry.get('status', '').upper() not in {'TRADING', 'ENABLED', ''}:
                continue

            native_symbol = entry['symbol']
            normalized = native_symbol.replace('_', '-').replace('/', '-')
            market_type = entry.get('type', 'spot').upper()
            if market_type == 'PERPETUAL':
                instrument_type = 'PERPETUAL'
            elif market_type in {'FUTURE', 'FUTURES'}:
                instrument_type = 'FUTURES'
            else:
                instrument_type = 'SPOT'

            precision = entry.get('precision', {})
            limits = entry.get('limits', {})
            amount_limits = limits.get('amount', {}) if isinstance(limits, dict) else {}
            min_amount_raw = amount_limits.get('min')
            min_amount = None
            if min_amount_raw is not None:
                min_amount = Decimal(str(min_amount_raw))

            market = BackpackMarket(
                normalized_symbol=normalized,
                native_symbol=native_symbol,
                instrument_type=instrument_type,
                price_precision=precision.get('price'),
                amount_precision=precision.get('amount'),
                min_amount=min_amount,
            )
            parsed[normalized] = market
        return parsed
