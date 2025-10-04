"""Backpack message router for translating websocket frames into callbacks."""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, Optional

from .metrics import BackpackMetrics

LOG = logging.getLogger("feedhandler")


class BackpackMessageRouter:
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
        self._trade_adapter = trade_adapter
        self._order_book_adapter = order_book_adapter
        self._trade_callback = trade_callback
        self._order_book_callback = order_book_callback
        self._ticker_adapter = ticker_adapter
        self._ticker_callback = ticker_callback
        self._metrics = metrics
        self._handlers: Dict[str, Callable[[dict], Awaitable[None]]] = {
            "trade": self._handle_trade,
            "trades": self._handle_trade,
            "l2": self._handle_order_book,
            "orderbook": self._handle_order_book,
            "l2_snapshot": self._handle_order_book,
            "l2_update": self._handle_order_book,
            "ticker": self._handle_ticker,
        }

    async def dispatch(self, message: str | dict) -> None:
        payload = json.loads(message) if isinstance(message, str) else message
        channel = payload.get("channel") or payload.get("type")
        if not channel:
            self._drop_payload("missing channel", payload)
            return

        handler = self._handlers.get(channel)
        if handler:
            await handler(payload)
        else:
            self._drop_payload(f"unknown channel '{channel}'", payload)

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

    def _drop_payload(self, reason: str, payload: dict) -> None:
        if self._metrics:
            self._metrics.record_parser_error()
            self._metrics.record_dropped_message()
        LOG.warning("Backpack router dropped payload: %s | payload=%s", reason, payload)
