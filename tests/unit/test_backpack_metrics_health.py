from __future__ import annotations

import time

from cryptofeed.exchanges.backpack.health import evaluate_health
from cryptofeed.exchanges.backpack.metrics import BackpackMetrics


def test_metrics_snapshot_and_health():
    metrics = BackpackMetrics()
    now = time.time()
    metrics.record_trade(now)
    metrics.record_orderbook("BTC-USDT", now, 42)
    snapshot = metrics.snapshot()

    assert snapshot["last_sequence"] == 42
    assert snapshot["ws_errors"] == 0

    report = evaluate_health(metrics, max_snapshot_age=60)
    assert report.healthy is True


def test_health_flags_auth_failure():
    metrics = BackpackMetrics()
    metrics.record_auth_failure()
    report = evaluate_health(metrics)
    assert report.healthy is False
    assert "authentication" in " ".join(report.reasons)
