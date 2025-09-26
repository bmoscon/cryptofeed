"""Metrics collection utilities for the Backpack native feed."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(slots=True)
class BackpackMetrics:
    """Simple counter-based metrics for Backpack feed observability."""

    ws_messages: int = 0
    ws_reconnects: int = 0
    ws_errors: int = 0
    auth_failures: int = 0
    dropped_messages: int = 0
    last_snapshot_timestamp: Optional[float] = None
    last_sequence: Optional[int] = None
    last_trade_timestamp: Optional[float] = None
    last_ticker_timestamp: Optional[float] = None
    symbol_snapshot_age: Dict[str, float] = field(default_factory=dict)

    def record_ws_message(self) -> None:
        self.ws_messages += 1

    def record_ws_reconnect(self) -> None:
        self.ws_reconnects += 1

    def record_ws_error(self) -> None:
        self.ws_errors += 1

    def record_auth_failure(self) -> None:
        self.auth_failures += 1

    def record_dropped_message(self) -> None:
        self.dropped_messages += 1

    def record_trade(self, timestamp: Optional[float]) -> None:
        if timestamp is not None:
            self.last_trade_timestamp = timestamp

    def record_ticker(self, timestamp: Optional[float]) -> None:
        if timestamp is not None:
            self.last_ticker_timestamp = timestamp

    def record_orderbook(self, symbol: str, timestamp: Optional[float], sequence: Optional[int]) -> None:
        now = time.time()
        if timestamp is not None:
            self.last_snapshot_timestamp = timestamp
            self.symbol_snapshot_age[symbol] = now - timestamp
        if sequence is not None:
            self.last_sequence = sequence

    def snapshot(self) -> Dict[str, object]:
        return {
            "ws_messages": self.ws_messages,
            "ws_reconnects": self.ws_reconnects,
            "ws_errors": self.ws_errors,
            "auth_failures": self.auth_failures,
            "dropped_messages": self.dropped_messages,
            "last_snapshot_timestamp": self.last_snapshot_timestamp,
            "last_sequence": self.last_sequence,
            "last_trade_timestamp": self.last_trade_timestamp,
            "last_ticker_timestamp": self.last_ticker_timestamp,
            "symbol_snapshot_age": dict(self.symbol_snapshot_age),
        }
