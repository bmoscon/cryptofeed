"""Backpack message router for translating websocket frames into callbacks."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from cryptofeed.exchanges.native.router import NativeMessageRouter

from .metrics import BackpackMetrics

LOG = logging.getLogger("feedhandler")


class BackpackMessageRouter(NativeMessageRouter):
    """Dispatch Backpack websocket messages to registered adapters and callbacks."""

    def __init__(
        self,
        *,
        trade_adapter,
        order_book_adapter,
        ticker_adapter=None,
        trade_callback: Optional[Callable[[Any, float], Awaitable[None]]] = None,
        order_book_callback: Optional[Callable[[Any, float], Awaitable[None]]] = None,
        ticker_callback: Optional[Callable[[Any, float], Awaitable[None]]] = None,
        metrics: Optional[BackpackMetrics] = None,
    ) -> None:
        super().__init__(metrics=metrics, logger=LOG)
        self._trade_adapter = trade_adapter
        self._order_book_adapter = order_book_adapter
        self._trade_callback = trade_callback
        self._order_book_callback = order_book_callback
        self._ticker_adapter = ticker_adapter
        self._ticker_callback = ticker_callback
        self._metrics = metrics
        self.register_handlers(["trade", "trades"], self._handle_trade)
        self.register_handlers(
            ["l2", "orderbook", "l2_snapshot", "l2_update"],
            self._handle_order_book,
        )
        self.register_handler("ticker", self._handle_ticker)

    async def _handle_trade(self, payload: dict) -> None:
        symbol = payload.get("symbol") or payload.get("topic")
        if not symbol:
            self._drop_payload("trade payload missing symbol", payload)
            return
        normalized_symbol = symbol.replace("_", "-")
        try:
            trade = self._trade_adapter.parse(payload, normalized_symbol=normalized_symbol)
        except (ValueError, KeyError, TypeError) as exc:
            self._drop_payload(f"trade parse error: {exc}", payload)
            return
        timestamp = getattr(trade, "timestamp", None) or 0.0
        if self._metrics:
            self._metrics.record_trade(timestamp)
        if not self._trade_callback:
            return
        await self._trade_callback(trade, timestamp)

    async def _handle_order_book(self, payload: dict) -> None:
        symbol = payload.get("symbol")
        if not symbol:
            self._drop_payload("orderbook payload missing symbol", payload)
            return
        normalized_symbol = symbol.replace("_", "-")

        if payload.get("snapshot", False) or payload.get("type") == "l2_snapshot":
            try:
                book = self._order_book_adapter.apply_snapshot(
                    normalized_symbol=normalized_symbol,
                    bids=payload.get("bids", []),
                    asks=payload.get("asks", []),
                    timestamp=payload.get("timestamp"),
                    sequence=payload.get("sequence"),
                    raw=payload,
                )
            except (ValueError, KeyError, TypeError) as exc:
                self._drop_payload(f"orderbook snapshot parse error: {exc}", payload)
                return
        else:
            try:
                book = self._order_book_adapter.apply_delta(
                    normalized_symbol=normalized_symbol,
                    bids=payload.get("bids"),
                    asks=payload.get("asks"),
                    timestamp=payload.get("timestamp"),
                    sequence=payload.get("sequence"),
                    raw=payload,
                )
            except KeyError:
                self._drop_payload("order book delta received before snapshot", payload)
                return
            except (ValueError, TypeError) as exc:
                self._drop_payload(f"orderbook delta parse error: {exc}", payload)
                return

        timestamp = getattr(book, "timestamp", None) or 0.0
        if self._metrics:
            self._metrics.record_orderbook(
                normalized_symbol,
                timestamp if timestamp else None,
                getattr(book, "sequence_number", None),
            )
        if not self._order_book_callback:
            return
        await self._order_book_callback(book, timestamp)

    async def _handle_ticker(self, payload: dict) -> None:
        if not self._ticker_adapter:
            return
        symbol = payload.get("symbol")
        if not symbol:
            self._drop_payload("ticker payload missing symbol", payload)
            return
        normalized_symbol = symbol.replace("_", "-")
        try:
            ticker = self._ticker_adapter.parse(payload, normalized_symbol=normalized_symbol)
        except (ValueError, KeyError, TypeError) as exc:
            self._drop_payload(f"ticker parse error: {exc}", payload)
            return
        timestamp = getattr(ticker, "timestamp", None) or 0.0
        if self._metrics:
            self._metrics.record_ticker(timestamp)
        if not self._ticker_callback:
            return
        await self._ticker_callback(ticker, timestamp)
