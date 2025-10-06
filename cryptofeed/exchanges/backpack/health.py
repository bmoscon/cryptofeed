"""Health evaluation for the Backpack native feed."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from .metrics import BackpackMetrics


@dataclass(slots=True)
class BackpackHealthReport:
    healthy: bool
    reasons: List[str]
    metrics: dict


def evaluate_health(metrics: BackpackMetrics, *, max_snapshot_age: float = 60.0) -> BackpackHealthReport:
    snapshot = metrics.snapshot()
    reasons: List[str] = []
    healthy = True

    if metrics.auth_failures > 0:
        healthy = False
        reasons.append("authentication failures detected")

    if snapshot["ws_errors"] > 0:
        healthy = False
        reasons.append("websocket errors observed")

    if snapshot["parser_errors"] > 0:
        healthy = False
        reasons.append("parser errors detected")

    last_snapshot = snapshot.get("last_snapshot_timestamp")
    if last_snapshot is not None:
        age = time.time() - last_snapshot
        if age > max_snapshot_age:
            healthy = False
            reasons.append(f"order book snapshot stale ({int(age)}s)")

    last_message = snapshot.get("last_message_timestamp")
    if last_message is not None:
        cadence = time.time() - last_message
        if cadence > max_snapshot_age:
            healthy = False
            reasons.append(f"no messages received in {int(cadence)}s")

    if snapshot["dropped_messages"] > 0:
        healthy = False
        reasons.append("dropped websocket messages")

    return BackpackHealthReport(healthy=healthy, reasons=reasons, metrics=snapshot)
