"""Reusable REST client helpers for native exchanges."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Callable

from yapic import json

from cryptofeed.connection import HTTPAsyncConn


class NativeRestError(RuntimeError):
    """Raised when native REST operations fail."""


@dataclass(slots=True)
class NativeOrderBookSnapshot:
    symbol: str
    bids: Iterable[Any]
    asks: Iterable[Any]
    sequence: Optional[int]
    timestamp_ms: Optional[int]


class NativeRestClient:
    """Thin async wrapper around HTTPAsyncConn with convenience helpers."""

    def __init__(
        self,
        *,
        exchange: str,
        exchange_id: str,
        http_conn_factory: Optional[Callable[[], HTTPAsyncConn]] = None,
    ) -> None:
        factory = http_conn_factory or (lambda: HTTPAsyncConn(exchange, exchange_id=exchange_id))
        self._conn: HTTPAsyncConn = factory()
        self._closed = False

    async def close(self) -> None:
        if not self._closed:
            await self._conn.close()
            self._closed = True

    async def read_json(self, url: str, *, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a GET request and parse the JSON payload."""
        text = await self._conn.read(url, params=params)
        try:
            return json.loads(text)
        except Exception as exc:  # pragma: no cover - yapic JSON raises generic Exception types
            raise NativeRestError(f"Unable to parse JSON payload from {url}: {exc}") from exc

    async def __aenter__(self) -> "NativeRestClient":
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
