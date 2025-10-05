"""Generic websocket message router utilities for native exchanges."""
from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional


class NativeMessageRouter:
    """Decode websocket payloads and dispatch to registered handlers."""

    def __init__(
        self,
        *,
        metrics: Any | None = None,
        logger: logging.Logger | None = None,
        channel_fields: Iterable[str] = ("channel", "type"),
    ) -> None:
        self._metrics = metrics
        self._logger = logger or logging.getLogger("feedhandler")
        self._handlers: Dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}
        self._channel_fields = tuple(channel_fields)

    def register_handler(
        self,
        channel: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        self._handlers[channel] = handler

    def register_handlers(
        self,
        channels: Iterable[str],
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        for channel in channels:
            self.register_handler(channel, handler)

    async def dispatch(self, message: dict[str, Any] | str) -> None:
        payload = self._coerce_payload(message)
        if not payload:
            return

        channel = self._extract_channel(payload)
        if not channel:
            self._drop_payload("missing channel", payload)
            return

        handler = self._handlers.get(channel)
        if not handler:
            self._drop_payload(f"unknown channel '{channel}'", payload)
            return

        await handler(payload)

    def _coerce_payload(self, message: dict[str, Any] | str) -> Optional[dict[str, Any]]:
        if isinstance(message, dict):
            return message
        try:
            payload = json.loads(message)
            if isinstance(payload, dict):
                return payload
        except Exception as exc:  # pragma: no cover - defensive logging
            self._drop_payload(f"invalid JSON payload: {exc}", {"raw": message})
            return None
        self._drop_payload("decoded payload is not an object", {"raw": message})
        return None

    def _extract_channel(self, payload: dict[str, Any]) -> Optional[str]:
        for field in self._channel_fields:
            value = payload.get(field)
            if value:
                return str(value)
        return None

    def _drop_payload(self, reason: str, payload: dict[str, Any]) -> None:
        self._record_parser_error()
        self._record_dropped_message()
        self._logger.warning("Native router dropped payload: %s | payload=%s", reason, payload)

    def _record_parser_error(self) -> None:
        recorder = getattr(self._metrics, "record_parser_error", None)
        if callable(recorder):
            recorder()

    def _record_dropped_message(self) -> None:
        recorder = getattr(self._metrics, "record_dropped_message", None)
        if callable(recorder):
            recorder()


__all__ = ["NativeMessageRouter"]

