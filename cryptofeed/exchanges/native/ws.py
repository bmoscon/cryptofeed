"""Reusable websocket session helpers for native exchanges."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Callable

from yapic import json

from cryptofeed.connection import WSAsyncConn
from cryptofeed.exchanges.native.metrics import NativeExchangeMetrics
from cryptofeed.exchanges.native.auth import Ed25519AuthHelper, NativeAuthError


class NativeWebsocketError(RuntimeError):
    """Raised when a native websocket session encounters an error."""


@dataclass(slots=True)
class NativeSubscription:
    channel: str
    symbols: Iterable[str]
    private: bool = False


class NativeWsSession:
    """Manages websocket connectivity, optional auth, and heartbeats."""

    def __init__(
        self,
        *,
        endpoint: str,
        exchange: str,
        exchange_id: str,
        conn_factory: Optional[Callable[[], WSAsyncConn]] = None,
        metrics: Optional[NativeExchangeMetrics] = None,
        auth_helper: Optional[Ed25519AuthHelper] = None,
        heartbeat_interval: float = 0.0,
    ) -> None:
        factory = conn_factory or (lambda: WSAsyncConn(endpoint, exchange, exchange_id=exchange_id))
        self._conn = factory()
        self._metrics = metrics
        self._auth_helper = auth_helper
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._connected = False
        self._last_auth_timestamp_us: Optional[int] = None

    async def open(self) -> None:
        if self._metrics and self._connected:
            self._metrics.record_ws_reconnect()
        await self._conn._open()
        self._connected = True
        self._start_heartbeat()

        if self._auth_helper:
            await self._send_auth()

    async def subscribe(self, subscriptions: Iterable[NativeSubscription]) -> None:
        if not self._connected:
            raise NativeWebsocketError("Websocket not open")

        payload = {
            "op": "subscribe",
            "channels": [
                {
                    "name": sub.channel,
                    "symbols": list(sub.symbols),
                    "private": sub.private,
                }
                for sub in subscriptions
            ],
        }
        await self._send(payload)

    async def read(self) -> Any:
        if not self._connected:
            raise NativeWebsocketError("Websocket not open")

        try:
            async for message in self._conn.read():
                if self._metrics:
                    self._metrics.record_ws_message()
                return message
        except Exception as exc:
            if self._metrics:
                self._metrics.record_ws_error()
            raise

        raise NativeWebsocketError("Websocket closed while reading")

    async def send(self, payload: dict) -> None:
        await self._send(payload)

    async def close(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        if self._connected:
            await self._conn.close()
            self._connected = False

    async def _send_auth(self) -> None:
        if not self._auth_helper:
            return
        try:
            headers = self._auth_helper.build_headers(method="GET", path="/")
        except NativeAuthError:
            if self._metrics:
                self._metrics.record_auth_failure()
            raise
        payload = {"op": "auth", "headers": headers}
        await self._send(payload)
        self._last_auth_timestamp_us = int(headers[self._auth_helper.DEFAULT_HEADERS["timestamp"]])

    def _start_heartbeat(self) -> None:
        if self._heartbeat_interval <= 0:
            return
        loop = asyncio.get_running_loop()
        self._heartbeat_task = loop.create_task(self._heartbeat())

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                await self._send({"op": "ping"})
                await self._on_heartbeat()
            except Exception:
                if self._metrics:
                    self._metrics.record_ws_error()
                raise

    async def _on_heartbeat(self) -> None:
        """Hook for subclasses to refresh auth or send maintenance messages."""

    async def _send(self, payload: dict) -> None:
        data = json.dumps(payload)
        send_fn = getattr(self._conn, "send", None)
        if callable(send_fn):
            await send_fn(data)
        else:
            await self._conn.write(data)
