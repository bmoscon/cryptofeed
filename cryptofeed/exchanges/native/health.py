"""Health evaluation helpers for native exchanges."""
from __future__ import annotations

from dataclasses import dataclass

from cryptofeed.exchanges.native.metrics import NativeExchangeMetrics


@dataclass(slots=True)
class NativeHealthReport:
    healthy: bool
    message: str


def evaluate_health(metrics: NativeExchangeMetrics, *, max_error_ratio: float = 0.1) -> NativeHealthReport:
    """Return a coarse health report based on websocket metrics."""

    total = metrics.ws_messages + metrics.ws_errors
    if total == 0:
        return NativeHealthReport(healthy=True, message="No activity yet")

    error_ratio = metrics.ws_errors / total
    if error_ratio > max_error_ratio:
        return NativeHealthReport(
            healthy=False,
            message=f"High websocket error ratio {error_ratio:.2%}",
        )

    if metrics.auth_failures:
        return NativeHealthReport(
            healthy=False,
            message=f"Authentication failures detected ({metrics.auth_failures})",
        )

    return NativeHealthReport(healthy=True, message="Healthy")
