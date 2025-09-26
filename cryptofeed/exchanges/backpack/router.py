"""Backpack message router for translating websocket frames into callbacks."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Dict, Optional

from cryptofeed.defines import L2_BOOK, TRADES


class BackpackMessageRouter:
    """Dispatch Backpack websocket messages to registered adapters and callbacks."""

    def __init__(
        self,
        *,
        trade_adapter,
        order_book_adapter,
        trade_callback: Optional[Callable[[Any, float], Awaitable[None]]] = None,
        order_book_callback: Optional[Callable[[Any, float], Awaitable[None]]] = None,
    ) -> None:
        self._trade_adapter = trade_adapter
        self._order_book_adapter = order_book_adapter
        self._trade_callback = trade_callback
        self._order_book_callback = order_book_callback
        self._handlers: Dict[str, Callable[[dict], Awaitable[None]]] = {
            "trade": self._handle_trade,
            "trades": self._handle_trade,
            "l2": self._handle_order_book,
            "orderbook": self._handle_order_book,
            "l2_snapshot": self._handle_order_book,
            "l2_update": self._handle_order_book,
        }

    async def dispatch(self, message: str | dict) -> None:
        payload = json.loads(message) if isinstance(message, str) else message
        channel = payload.get("channel") or payload.get("type")
        if not channel:
            return

        handler = self._handlers.get(channel)
        if handler:
            await handler(payload)

    async def _handle_trade(self, payload: dict) -> None:
        if not self._trade_callback:
            return
        symbol = payload.get("symbol") or payload.get("topic")
        normalized_symbol = symbol.replace("_", "-") if symbol else symbol
        trade = self._trade_adapter.parse(payload, normalized_symbol=normalized_symbol)
        timestamp = getattr(trade, "timestamp", None) or 0.0
        await self._trade_callback(trade, timestamp)

    async def _handle_order_book(self, payload: dict) -> None:
        if not self._order_book_callback:
            return
        symbol = payload.get("symbol")
        normalized_symbol = symbol.replace("_", "-") if symbol else symbol

        if payload.get("snapshot", False) or payload.get("type") == "l2_snapshot":
            book = self._order_book_adapter.apply_snapshot(
                normalized_symbol=normalized_symbol,
                bids=payload.get("bids", []),
                asks=payload.get("asks", []),
                timestamp=payload.get("timestamp"),
                sequence=payload.get("sequence"),
                raw=payload,
            )
        else:
            book = self._order_book_adapter.apply_delta(
                normalized_symbol=normalized_symbol,
                bids=payload.get("bids"),
                asks=payload.get("asks"),
                timestamp=payload.get("timestamp"),
                sequence=payload.get("sequence"),
                raw=payload,
            )

        timestamp = getattr(book, "timestamp", None) or 0.0
        await self._order_book_callback(book, timestamp)
