"""Backpack WebSocket session abstraction leveraging cryptofeed WSAsyncConn."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from yapic import json

from cryptofeed.connection import WSAsyncConn
from cryptofeed.exchanges.backpack.auth import BackpackAuthHelper, BackpackAuthError
from cryptofeed.exchanges.backpack.config import BackpackConfig
from cryptofeed.exchanges.backpack.metrics import BackpackMetrics


class BackpackWebsocketError(RuntimeError):
    """Raised for Backpack websocket lifecycle errors."""


@dataclass(slots=True)
class BackpackSubscription:
    channel: str
    symbols: Iterable[str]
    private: bool = False


class BackpackWsSession:
    """Manages Backpack websocket connectivity, authentication, and subscriptions."""

    def __init__(
        self,
        config: BackpackConfig,
        *,
        auth_helper: BackpackAuthHelper | None = None,
        metrics: Optional[BackpackMetrics] = None,
        conn_factory=None,
        heartbeat_interval: float = 15.0,
    ) -> None:
        self._config = config
        self._auth_helper = auth_helper
        if self._config.enable_private_channels and self._auth_helper is None:
            self._auth_helper = BackpackAuthHelper(self._config)

        self._metrics = metrics
        factory = conn_factory or (lambda: WSAsyncConn(self._config.ws_endpoint, "backpack", exchange_id=config.exchange_id))
        self._conn = factory()

        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._connected = False
        self._last_auth_timestamp_us: Optional[int] = None
        self._private_channels_active = False

    async def open(self) -> None:
        if self._connected and self._metrics:
            self._metrics.record_ws_reconnect()
        open_fn = getattr(self._conn, "open", None)
        if callable(open_fn):
            await open_fn()
        else:
            await self._conn._open()
        self._connected = True
        self._start_heartbeat()

        if self._auth_helper:
            try:
                await self._send_auth()
            except BackpackAuthError:
                if self._metrics:
                    self._metrics.record_auth_failure()
                raise

    async def subscribe(self, subscriptions: Iterable[BackpackSubscription]) -> None:
        if not self._connected:
            raise BackpackWebsocketError("Websocket not open")

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

        if any(sub.private for sub in subscriptions):
            self._private_channels_active = True
            await self._maybe_refresh_auth(force=True)

    async def read(self) -> Any:
        if not self._connected:
            raise BackpackWebsocketError("Websocket not open")

        try:
            read_fn = getattr(self._conn, "receive", None)
            if callable(read_fn):
                message = await read_fn()
                if self._metrics:
                    self._metrics.record_ws_message()
                return message

            # Fallback to AsyncIterable interface from WSAsyncConn
            async for message in self._conn.read():
                if self._metrics:
                    self._metrics.record_ws_message()
                return message
        except Exception as exc:
            if self._metrics:
                self._metrics.record_ws_error()
            raise

        raise BackpackWebsocketError("Websocket closed while reading")

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
        try:
            timestamp = self._auth_helper._current_timestamp_us()
            headers = self._auth_helper.build_headers(method="GET", path="/ws/auth", timestamp_us=timestamp)
        except Exception as exc:  # pragma: no cover - defensive, metrics capture auth failures
            raise BackpackAuthError(str(exc)) from exc

        payload = {"op": "auth", "headers": headers}
        await self._send(payload)
        self._last_auth_timestamp_us = timestamp

    async def _send(self, payload: dict) -> None:
        data = json.dumps(payload)
        send_fn = getattr(self._conn, "send", None)
        if callable(send_fn):
            await send_fn(data)
        else:
            await self._conn.write(data)

    async def send(self, payload: dict) -> None:
        await self._send(payload)

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
                await self._maybe_refresh_auth()
            except Exception as exc:  # pragma: no cover - heartbeat failure best effort
                if self._metrics:
                    self._metrics.record_ws_error()
                raise BackpackWebsocketError(f"Heartbeat failed: {exc}") from exc

    async def _maybe_refresh_auth(self, *, force: bool = False) -> None:
        if not self._auth_helper or not self._private_channels_active:
            return

        now_us = self._auth_helper._current_timestamp_us()
        window_us = self._config.window_ms * 1000
        if force or self._last_auth_timestamp_us is None:
            await self._send_auth()
            return

        elapsed = now_us - self._last_auth_timestamp_us
        if elapsed >= window_us // 2:
            await self._send_auth()


from contextlib import suppress  # noqa: E402  (import after class definition for readability)
