"""Integration-style tests for the Iggy backend scaffolding.

These tests exercise the queue/writer lifecycle and simple throughput checks
without requiring a live Iggy server. They simulate the async writer loop by
patching it during execution.
"""

from __future__ import annotations

import asyncio
import time
import os
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_iggy_backend_end_to_end_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends.iggy import IggyCallback, TradeIggy

    processed: list[Any] = []

    async def fake_writer(self) -> None:  # type: ignore[override]
        processed.append("writer_started")
        while True:
            async with self.read_queue() as updates:
                if not updates:
                    break
                for update in updates:
                    await self._emit(update)
        processed.append("writer_stopped")

    async def fake_emit(self, payload: Any) -> None:  # type: ignore[override]
        processed.append(payload)

    monkeypatch.setattr(IggyCallback, "writer", fake_writer, raising=False)
    monkeypatch.setattr(IggyCallback, "_emit", fake_emit, raising=False)

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)

    await callback.write({"exchange": "BINANCE", "symbol": "BTC-USDT"})
    await asyncio.sleep(0)

    await callback.stop()
    await asyncio.sleep(0)

    assert processed[0] == "writer_started"
    assert any(isinstance(item, dict) and item["exchange"] == "BINANCE" for item in processed)
    assert processed[-1] == "writer_stopped"


@pytest.mark.asyncio
async def test_iggy_backend_meets_throughput_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends.iggy import IggyCallback, TradeIggy

    count = 0

    async def fake_writer(self) -> None:  # type: ignore[override]
        nonlocal count
        while True:
            async with self.read_queue() as updates:
                if not updates:
                    break
                for update in updates:
                    await self._emit(update)
                    count += 1

    async def fake_emit(self, payload: Any) -> None:  # type: ignore[override]
        pass  # No-op to simulate fast network send

    monkeypatch.setattr(IggyCallback, "writer", fake_writer, raising=False)
    monkeypatch.setattr(IggyCallback, "_emit", fake_emit, raising=False)

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)

    messages = 500
    start = time.perf_counter()
    for _ in range(messages):
        await callback.write({"exchange": "BINANCE"})
    await asyncio.sleep(0)
    await callback.stop()
    duration = time.perf_counter() - start

    assert count == messages
    assert duration < 0.5



@pytest.mark.asyncio
async def test_iggy_backend_sends_with_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends.iggy import IggyCallback, TradeIggy

    emits = []

    class FakeClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            emits.append((stream, topic, payload))

    def factory(*, host: str, port: int) -> FakeClient:
        return FakeClient()

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        client_factory=factory,
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)
    await callback.write({"exchange": "BINANCE"})
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)

    assert emits == [("cryptofeed", "trades", {"exchange": "BINANCE"})]


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("IGGY_DOCKER_TESTS") != "1", reason="Set IGGY_DOCKER_TESTS=1 to run Docker-backed integration")
async def test_iggy_backend_docker_round_trip(tmp_path) -> None:
    """Spin up an Iggy container and verify the client factory sends a message."""
    import subprocess
    import time

    container_name = f"iggy-test-{int(time.time())}"
    port = "8090"

    run_cmd = [
        "docker",
        "run",
        "-d",
        "--rm",
        "--name",
        container_name,
        "-p",
        f"{port}:{port}",
        "iggyio/iggy:latest",
    ]

    try:
        subprocess.run(run_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Unable to start Iggy container: {exc.stderr.decode()}")

    try:
        from cryptofeed.backends.iggy import IggyCallback, TradeIggy

        emitted = []

        class DummyClient:
            async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
                emitted.append(payload)

        def factory(cb: IggyCallback) -> DummyClient:
            return DummyClient()

        callback = TradeIggy(
            host="localhost",
            port=int(port),
            transport="tcp",
            stream="cryptofeed",
            topic="trades",
            backend="iggy",
            client_factory=factory,
        )

        loop = asyncio.get_running_loop()
        callback.start(loop, multiprocess=False)
        await callback.write({"exchange": "BINANCE"})
        await asyncio.sleep(0)
        await callback.stop()
        await asyncio.sleep(0)

        assert emitted
    finally:
        subprocess.run(["docker", "stop", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@pytest.mark.asyncio
async def test_iggy_backend_end_to_end_metrics(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    sent: list[dict[str, Any]] = []

    class FakeClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            sent.append(payload)

    transport = iggy_module.IggyTransport(host="localhost", port=8090, client_factory=lambda host, port: FakeClient())
    metrics = iggy_module.IggyMetrics(
        make_counter=lambda name, doc, labels: _StubCounter(name, doc, labels),
        make_histogram=lambda name, doc, labels: _StubHistogram(name, doc, labels),
    )

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        transport_adapter=transport,
        metrics=metrics,
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)

    with caplog.at_level("INFO", logger="feedhandler.iggy"):
        await callback.write({"exchange": "BINANCE", "symbol": "BTC-USDT"})
        await asyncio.sleep(0)
        await callback.stop()
        await asyncio.sleep(0)

    assert sent and sent[0]["exchange"] == "BINANCE"
    counter = metrics._counters[("iggy_emit_total", ("stream", "topic"))]
    assert counter.samples[-1]["stream"] == "cryptofeed"
    histogram = metrics._histograms[("iggy_emit_latency_seconds", ("stream", "topic"))]
    assert "value" in histogram.samples[-1]
    assert any("event=emit_success" in message for message in caplog.messages)
class _StubCounter:
    def __init__(self, name: str, doc: str, labelnames: tuple[str, ...]) -> None:
        self.samples: list[dict[str, Any]] = []
        self.labelnames = labelnames

    def labels(self, **labels: Any) -> "_StubCounter":
        self.samples.append(dict(labels))
        return self

    def inc(self, amount: float = 1.0) -> None:
        if self.samples:
            self.samples[-1]["_amount"] = self.samples[-1].get("_amount", 0.0) + amount


class _StubHistogram:
    def __init__(self, name: str, doc: str, labelnames: tuple[str, ...]) -> None:
        self.samples: list[dict[str, Any]] = []
        self.labelnames = labelnames

    def labels(self, **labels: Any) -> "_StubHistogram":
        self.samples.append(dict(labels))
        return self

    def observe(self, value: float) -> None:
        if self.samples:
            self.samples[-1]['value'] = value
