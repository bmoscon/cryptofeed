"""Simple metrics container for native exchange integrations."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NativeExchangeMetrics:
    """Tracks lightweight counters for native exchange transports."""

    ws_messages: int = 0
    ws_errors: int = 0
    ws_reconnects: int = 0
    auth_failures: int = 0

    def record_ws_message(self) -> None:
        self.ws_messages += 1

    def record_ws_error(self) -> None:
        self.ws_errors += 1

    def record_ws_reconnect(self) -> None:
        self.ws_reconnects += 1

    def record_auth_failure(self) -> None:
        self.auth_failures += 1
