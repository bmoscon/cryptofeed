"""Proxy-aware REST transport for CCXT exchanges."""
from __future__ import annotations

import asyncio
import inspect
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, Optional

from cryptofeed.proxy import get_proxy_injector, log_proxy_usage

from ..context import CcxtExchangeContext
from ..generic import (
    CcxtMetadataCache,
    CcxtUnavailable,
    OrderBookSnapshot,
    _resolve_dynamic_import,
)


class CcxtRestTransport:
    """REST transport for order book snapshots."""

    def __init__(
        self,
        cache: CcxtMetadataCache,
        *,
        context: Optional[CcxtExchangeContext] = None,
        require_auth: bool = False,
        auth_callbacks: Optional[Iterable[Callable[[Any], Any]]] = None,
        max_retries: int = 3,
        base_retry_delay: float = 0.5,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._cache = cache
        self._client: Optional[Any] = None
        self._context = context
        self._require_auth = require_auth
        self._auth_callbacks = list(auth_callbacks or [])
        self._authenticated = False
        self._max_retries = max(1, max_retries)
        self._base_retry_delay = max(0.0, base_retry_delay)
        self._log = logger or logging.getLogger('feedhandler')
        self._sleep = asyncio.sleep

    async def __aenter__(self) -> "CcxtRestTransport":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        await self.close()

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                async_support = _resolve_dynamic_import()("ccxt.async_support")
                ctor = getattr(async_support, self._cache.exchange_id)
            except Exception as exc:  # pragma: no cover - import failure path
                raise CcxtUnavailable(
                    f"ccxt.async_support.{self._cache.exchange_id} unavailable"
                ) from exc
            kwargs = self._client_kwargs()
            if not kwargs:
                self._client = ctor()
            else:
                try:
                    self._client = ctor(**kwargs)
                except TypeError:
                    self._client = ctor()
                    try:
                        self._client.__dict__.setdefault('_cryptofeed_init_kwargs', {}).update(kwargs)
                    except Exception:  # pragma: no cover - defensive fallback
                        pass
        return self._client

    def _client_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if self._context:
            kwargs.update(self._context.ccxt_options)
        proxy_url = None
        if self._context and self._context.http_proxy_url:
            proxy_url = self._context.http_proxy_url
        else:
            injector = get_proxy_injector()
            if injector is not None:
                proxy_url = injector.get_http_proxy_url(self._cache.exchange_id)
        if proxy_url:
            kwargs.setdefault('aiohttp_proxy', proxy_url)
            kwargs.setdefault('proxies', {'http': proxy_url, 'https': proxy_url})
            log_proxy_usage(transport='rest', exchange_id=self._cache.exchange_id, proxy_url=proxy_url)
        kwargs.setdefault('enableRateLimit', kwargs.get('enableRateLimit', True))
        return kwargs

    async def _authenticate_client(self, client: Any) -> None:
        if not self._require_auth or self._authenticated:
            return
        checker = getattr(client, 'check_required_credentials', None)
        if checker is not None:
            try:
                checker()
            except ValueError as exc:
                raise RuntimeError("invalid or incomplete credentials") from exc
        for callback in self._auth_callbacks:
            result = callback(client)
            if inspect.isawaitable(result):
                await result
        self._authenticated = True

    async def order_book(self, symbol: str, *, limit: Optional[int] = None) -> OrderBookSnapshot:
        await self._cache.ensure()
        client = await self._ensure_client()
        await self._authenticate_client(client)
        request_symbol = self._cache.request_symbol(symbol)
        last_exc: Optional[Exception] = None
        for attempt in range(1, self._max_retries + 1):
            try:
                book = await client.fetch_order_book(request_symbol, limit=limit)
                break
            except Exception as exc:  # pragma: no cover - specific exception types logged
                last_exc = exc
                if attempt == self._max_retries:
                    raise
                delay = self._retry_delay(attempt)
                self._log.warning(
                    "ccxt-rest: retrying order_book after error",
                    extra={
                        'exchange': self._cache.exchange_id,
                        'symbol': symbol,
                        'attempt': attempt,
                        'max_retries': self._max_retries,
                        'error': str(exc),
                    },
                )
                await self._sleep(delay)
        else:  # pragma: no cover - defensive, loop always breaks or raises
            raise last_exc if last_exc else RuntimeError("order_book failed without exception")
        timestamp_raw = book.get("timestamp") or book.get("datetime")
        timestamp = float(timestamp_raw) / 1000.0 if timestamp_raw else None
        return OrderBookSnapshot(
            symbol=symbol,
            bids=[(Decimal(str(price)), Decimal(str(amount))) for price, amount in book.get("bids", [])],
            asks=[(Decimal(str(price)), Decimal(str(amount))) for price, amount in book.get("asks", [])],
            timestamp=timestamp,
            sequence=book.get("nonce"),
        )

    def _retry_delay(self, attempt: int) -> float:
        return self._base_retry_delay * (2 ** (attempt - 1))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


__all__ = ["CcxtRestTransport"]
