"""Backpack REST client built on cryptofeed HTTPAsyncConn."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from yapic import json

from cryptofeed.connection import HTTPAsyncConn
from cryptofeed.exchanges.backpack.config import BackpackConfig


class BackpackRestError(RuntimeError):
    """Raised when Backpack REST operations fail."""


@dataclass(slots=True)
class BackpackOrderBookSnapshot:
    symbol: str
    bids: list[list[str | float]]
    asks: list[list[str | float]]
    sequence: Optional[int]
    timestamp_ms: Optional[int]


class BackpackRestClient:
    """Thin async wrapper around HTTPAsyncConn with Backpack-specific helpers."""

    MARKETS_PATH = "/api/v1/markets"
    L2_DEPTH_PATH = "/api/v1/depth"

    def __init__(self, config: BackpackConfig, *, http_conn_factory=None) -> None:
        self._config = config
        factory = http_conn_factory or (lambda: HTTPAsyncConn("backpack", exchange_id=config.exchange_id))
        self._conn: HTTPAsyncConn = factory()
        self._closed = False

        if self._config.proxies and self._config.proxies.url:
            # Ensure override proxy is respected for the entire session
            self._conn.proxy = self._config.proxies.url

    async def close(self) -> None:
        if not self._closed:
            await self._conn.close()
            self._closed = True

    async def fetch_markets(self) -> Iterable[Dict[str, Any]]:
        """Return Backpack market metadata list."""
        url = f"{self._config.rest_endpoint}{self.MARKETS_PATH}"
        text = await self._conn.read(url)
        try:
            data = json.loads(text)
        except Exception as exc:  # pragma: no cover - yapic JSON raises generic Exception types
            raise BackpackRestError(f"Unable to parse markets payload: {exc}") from exc
        if not isinstance(data, (list, tuple)):
            raise BackpackRestError("Markets endpoint returned unexpected payload")
        return data

    async def fetch_order_book(self, *, native_symbol: str, depth: int = 50) -> BackpackOrderBookSnapshot:
        """Fetch an order book snapshot for the provided native Backpack symbol."""
        url = f"{self._config.rest_endpoint}{self.L2_DEPTH_PATH}"
        params = {"symbol": native_symbol, "limit": depth}
        text = await self._conn.read(url, params=params)
        try:
            data = json.loads(text)
        except Exception as exc:  # pragma: no cover
            raise BackpackRestError(f"Unable to parse order book payload: {exc}") from exc

        if not isinstance(data, dict) or "bids" not in data or "asks" not in data:
            raise BackpackRestError("Malformed order book payload")

        return BackpackOrderBookSnapshot(
            symbol=native_symbol,
            bids=data.get("bids", []),
            asks=data.get("asks", []),
            sequence=data.get("sequence"),
            timestamp_ms=data.get("timestamp"),
        )

    async def __aenter__(self) -> "BackpackRestClient":
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
