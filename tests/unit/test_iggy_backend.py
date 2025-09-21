"""Behavior-driven scaffolding for the upcoming Iggy backend.

These tests outline the acceptance criteria for the Apache Iggy transport. They
are initially marked as xfail to drive the TDD cycle documented in
`docs/iggy_backend.md`.
"""

from __future__ import annotations

import asyncio
from typing import Any
import types
from pathlib import Path

import pytest


def test_iggy_callback_exposes_configuration() -> None:
    """The Iggy callback must expose core configuration and derive from BackendQueue."""
    from cryptofeed.backends.backend import BackendQueue
    from cryptofeed.backends.iggy import IggyCallback

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    assert isinstance(callback, BackendQueue)
    assert callback.host == "localhost"
    assert callback.port == 8090
    from cryptofeed.backends import iggy as iggy_module
    assert isinstance(callback.transport, iggy_module.IggyTransport)
    assert callback.transport._host == "localhost"
    assert callback.transport._port == 8090
    assert callback.stream == "cryptofeed"
    assert callback.topic == "trades"


@pytest.mark.asyncio
async def test_iggy_callback_supports_multiprocessing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Iggy callback should integrate with BackendQueue start/stop and drain writes."""
    from cryptofeed.backends.iggy import IggyCallback

    events: list[Any] = []

    async def fake_writer(self) -> None:  # type: ignore[override]
        events.append("started")
        while self.running:
            async with self.read_queue() as updates:
                if not updates:
                    break
                events.extend(updates)
        events.append("stopped")

    monkeypatch.setattr(IggyCallback, "writer", fake_writer, raising=False)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)
    await callback.write({"exchange": "BINANCE"})
    await asyncio.sleep(0)

    await callback.stop()
    await asyncio.sleep(0)

    assert events[0] == "started"
    assert {"exchange": "BINANCE"} in events
    assert events[-1] == "stopped"


@pytest.mark.asyncio
async def test_iggy_trade_payload_matches_kafka_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kafka and Iggy trade payloads should match core fields and timestamps in JSON mode."""
    from cryptofeed.backends.iggy import TradeIggy

    captured: list[Any] = []

    async def fake_emit(self, data: Any) -> None:
        captured.append(data)

    async def fake_writer(self) -> None:  # type: ignore[override]
        while True:
            async with self.read_queue() as updates:
                if not updates:
                    break
                for update in updates:
                    await self._emit(update)

    monkeypatch.setattr(TradeIggy, "_emit", fake_emit, raising=False)
    monkeypatch.setattr(TradeIggy, "writer", fake_writer, raising=False)

    class DummyTrade:
        timestamp = None

        def to_dict(self, *, numeric_type=float, none_to=None):  # type: ignore[override]
            return {"exchange": "BINANCE", "symbol": "BTC-USDT", "price": 100.0}

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    assert getattr(TradeIggy, "default_key", None) == "trades"
    assert callback.key == "trades"

    callback.start(asyncio.get_running_loop(), multiprocess=False)
    await callback(DummyTrade(), receipt_timestamp=1234.0)
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)

    assert captured, "write should be invoked"
    payload = captured[0]
    assert payload["exchange"] == "BINANCE"
    assert payload["symbol"] == "BTC-USDT"
    assert payload["price"] == 100.0
    assert payload["receipt_timestamp"] == 1234.0
    assert payload["timestamp"] == 1234.0


@pytest.mark.asyncio
async def test_iggy_book_snapshot_follows_configured_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Order book snapshots should follow the configured cadence."""
    from cryptofeed.backends.iggy import BookIggy

    captured: list[Any] = []

    async def fake_write(self, data: dict) -> None:
        captured.append(data)

    async def fake_writer(self) -> None:  # type: ignore[override]
        while True:
            async with self.read_queue() as updates:
                if not updates:
                    break
                for update in updates:
                    await self._emit(update)

    monkeypatch.setattr(BookIggy, "_emit", fake_write, raising=False)
    monkeypatch.setattr(BookIggy, "writer", fake_writer, raising=False)

    class DummyBook:
        def __init__(self) -> None:
            self.symbol = "BTC-USDT"
            self.timestamp = None
            self.delta = {"asks": [["100", "1"]], "bids": []}

        def to_dict(self, *, delta: bool = False, numeric_type=float, none_to=None):  # type: ignore[override]
            payload = {"exchange": "BINANCE", "symbol": self.symbol}
            payload["delta"] = self.delta if delta else self.delta
            return payload

    callback = BookIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="book",
        backend="iggy",
        snapshot_interval=2,
    )

    callback.start(asyncio.get_running_loop(), multiprocess=False)
    await callback(DummyBook(), receipt_timestamp=1.0)
    await callback(DummyBook(), receipt_timestamp=2.0)
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)

    assert len(captured) == 3, "Two deltas and one snapshot expected when interval reached"
    snapshot = captured[-1]
    assert "delta" not in snapshot
    assert snapshot["receipt_timestamp"] == 2.0
    assert snapshot["timestamp"] == 2.0


def test_iggy_backend_configuration_validation() -> None:
    """Config surface should reject incomplete or conflicting options."""
    from cryptofeed.backends.iggy import IggyCallback

    with pytest.raises(ValueError, match="host must be provided"):
        IggyCallback(
            host="",
            port=0,
            transport="tcp",
            stream="",
            topic="trades",
            backend="iggy",
        )

    with pytest.raises(ValueError, match="unsupported transport"):
        IggyCallback(
            host="localhost",
            port=8090,
            transport="smtp",
            stream="cryptofeed",
            topic="trades",
            backend="iggy",
        )

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        serializer="binary",
    )
    assert callback.serializer == "binary"


@pytest.mark.asyncio
async def test_iggy_binary_serialization_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """Binary mode must preserve payload types and surface unsupported data."""
    from cryptofeed.backends.iggy import TradeIggy

    captured: list[Any] = []

    async def fake_emit(self, data: Any) -> None:
        captured.append(data)

    async def fake_writer(self) -> None:  # type: ignore[override]
        while True:
            async with self.read_queue() as updates:
                if not updates:
                    break
                for update in updates:
                    await self._emit(update)

    monkeypatch.setattr(TradeIggy, "_emit", fake_emit, raising=False)
    monkeypatch.setattr(TradeIggy, "writer", fake_writer, raising=False)

    class DummyTrade:
        timestamp = None

        def to_dict(self, *, numeric_type=float, none_to=None):  # type: ignore[override]
            return {"exchange": "BINANCE", "symbol": "BTC-USDT", "price": 100.0}

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        serializer="binary",
    )

    payload = DummyTrade()

    callback.start(asyncio.get_running_loop(), multiprocess=False)
    with pytest.raises(TypeError):
        await callback(payload, receipt_timestamp=1.0)
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)

    dummy_serializer_called = False

    def binary_serializer(data: dict) -> bytes:
        nonlocal dummy_serializer_called
        dummy_serializer_called = True
        return b"binary" + bytes(str(data), "utf-8")

    callback = TradeIggy(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        serializer="binary",
        value_serializer=binary_serializer,
    )

    callback.start(asyncio.get_running_loop(), multiprocess=False)
    await callback(payload, receipt_timestamp=2.0)
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)
    assert dummy_serializer_called
    assert captured  # write should be invoked with binary bytes
    assert isinstance(captured[-1], bytes)


def test_iggy_backend_emits_structured_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured logging should emit expected fields without secrets."""
    import logging
    from cryptofeed.backends.iggy import IggyCallback

    records: list[logging.LogRecord] = []

    class CapturingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = CapturingHandler()
    logger = logging.getLogger("feedhandler.iggy")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    callback.log_connection_event("connect")
    callback.log_connection_event("error", detail="auth failed")

    assert records
    last = records[-1]
    assert "auth" in last.getMessage()
    assert "host=localhost" in last.getMessage()
    assert "password" not in last.getMessage()

    logger.removeHandler(handler)



@pytest.mark.asyncio
async def test_iggy_writer_drains_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends.iggy import IggyCallback

    emitted: list[Any] = []

    async def fake_emit(self, payload: Any) -> None:
        emitted.append(payload)

    monkeypatch.setattr(IggyCallback, "_emit", fake_emit, raising=False)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    loop = asyncio.get_running_loop()
    callback.start(loop, multiprocess=False)
    await callback.write({"exchange": "BINANCE"})
    await asyncio.sleep(0)
    await callback.stop()
    await asyncio.sleep(0)

    assert emitted == [{"exchange": "BINANCE"}]
    assert callback.running is False


@pytest.mark.asyncio
async def test_iggy_emit_uses_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    calls: list[tuple[str, str, Any]] = []

    class FakeClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            calls.append((stream, topic, payload))

    transport = iggy_module.IggyTransport(host="localhost", port=8090, client_factory=lambda host, port: FakeClient())

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        transport_adapter=transport,
    )

    await callback._emit({"exchange": "BINANCE"})

    assert calls == [("cryptofeed", "trades", {"exchange": "BINANCE"})]


@pytest.mark.asyncio
async def test_iggy_emit_retries_before_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    attempts = 0

    class FlakyClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise RuntimeError("temporary failure")

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", lambda _: no_sleep(0), raising=False)

    metrics = iggy_module.IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))
    transport = iggy_module.IggyTransport(host="localhost", port=8090, client_factory=lambda host, port: FlakyClient())

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        retry_attempts=2,
        transport_adapter=transport,
        metrics=metrics,
    )

    await callback._emit({"exchange": "BINANCE"})
    assert attempts == 2


@pytest.mark.asyncio
async def test_iggy_emit_raises_without_client() -> None:
    from cryptofeed.backends.iggy import IggyCallback

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        retry_attempts=1,
    )

    with pytest.raises(RuntimeError, match="Install iggy-py"):
        await callback._emit({"exchange": "BINANCE"})


@pytest.mark.asyncio
async def test_iggy_client_factory_creates_client() -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    created = []

    class FakeClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            created.append((stream, topic, payload))

    def factory(*, host: str, port: int) -> FakeClient:
        assert host == "localhost"
        assert port == 8090
        return FakeClient()

    transport = iggy_module.IggyTransport(host="localhost", port=8090, client_factory=factory)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        client_factory=factory,
        transport_adapter=transport,
    )

    await callback._emit({"exchange": "BINANCE"})

    assert created == [("cryptofeed", "trades", {"exchange": "BINANCE"})]


@pytest.mark.asyncio
async def test_iggy_default_client_factory_requires_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    from cryptofeed.backends.iggy import IggyCallback

    monkeypatch.setitem(sys.modules, "iggy.client", None)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    with pytest.raises(RuntimeError, match="Install iggy-py"):
        await callback._emit({"exchange": "BINANCE"})


@pytest.mark.asyncio
async def test_iggy_default_client_factory_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    import sys
    from cryptofeed.backends.iggy import IggyCallback

    client_module = types.SimpleNamespace()

    class DummyClient:
        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port
            self.sent: list[Any] = []

        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            self.sent.append((stream, topic, payload))

    def create_client(*, host: str, port: int, **kwargs) -> DummyClient:
        return DummyClient(host, port)

    client_module.Client = DummyClient
    client_module.connect = create_client

    module = types.ModuleType("iggy.client")
    module.Client = DummyClient
    module.connect = create_client

    monkeypatch.setitem(sys.modules, "iggy.client", module)

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
    )

    await callback._emit({"exchange": "BINANCE"})
    assert callback.transport.client().sent == [("cryptofeed", "trades", {"exchange": "BINANCE"})]


@pytest.mark.asyncio
async def test_iggy_metrics_increment(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    metrics = iggy_module.IggyMetrics(
        make_counter=lambda *a, **k: _StubCounter(*a, **k),
        make_histogram=lambda *a, **k: _StubHistogram(*a, **k),
    )

    class DummyClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            return None

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        client_factory=lambda host, port: DummyClient(),
        metrics=metrics,
    )

    await callback._emit({"exchange": "BINANCE"})

    counter = metrics._counters[("iggy_emit_total", ("stream", "topic"))]
    assert counter.samples[-1]["stream"] == "cryptofeed"


def test_iggy_prometheus_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    class FakeCounter:
        def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...], registry=None) -> None:
            self.labelnames = labelnames
            self.samples: list[dict[str, Any]] = []

        def labels(self, **kwargs: Any) -> "FakeCounter":
            self.samples.append(kwargs)
            return self

        def inc(self, amount: float = 1.0) -> None:
            if self.samples:
                self.samples[-1]["_amount"] = self.samples[-1].get("_amount", 0) + amount

    class FakeHistogram:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def labels(self, **labels: Any):
            return types.SimpleNamespace(observe=lambda value: None)

    registry: dict[str, Any] = {}
    monkeypatch.setattr(iggy_module, "_PROM_COUNTERS", {})
    monkeypatch.setattr(iggy_module, "_PROM_HISTOGRAMS", {})
    monkeypatch.setattr(iggy_module, "PROMETHEUS_REGISTRY", registry)
    monkeypatch.setattr(iggy_module, "_MAKE_COUNTER", lambda name, doc, labels: FakeCounter(name, doc, labels, registry))
    monkeypatch.setattr(iggy_module, "_MAKE_HISTOGRAM", lambda name, doc, labels: FakeHistogram(name, doc, labels, registry))

    metrics = iggy_module.IggyMetrics(make_counter=lambda name, doc, labels: _StubCounter(name, doc, labels), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        client_factory=lambda host, port: types.SimpleNamespace(send=lambda **_: None),
        metrics=metrics,
    )

    callback.metrics.increment_emit_success(stream="cryptofeed", topic="trades")

    counter = callback.metrics._counters[("iggy_emit_total", ("stream", "topic"))]
    assert counter.samples[-1]["stream"] == "cryptofeed"
    assert counter.samples[-1]["topic"] == "trades"
    assert counter.samples[-1]["_amount"] == 1.0


@pytest.mark.asyncio
async def test_iggy_latency_histogram(monkeypatch: pytest.MonkeyPatch) -> None:
    import types
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    class FakeHistogram:
        def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...], registry=None) -> None:
            self.samples: list[dict[str, Any]] = []

        def labels(self, **labels: Any) -> "FakeHistogram":
            self.samples.append(labels)
            return self

        def observe(self, value: float) -> None:
            if self.samples:
                self.samples[-1]['value'] = value

    class FakeCounter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def labels(self, **labels: Any):
            return types.SimpleNamespace(inc=lambda amount=1.0: None)

    registry: dict[str, Any] = {}
    monkeypatch.setattr(iggy_module, "_PROM_COUNTERS", {})
    monkeypatch.setattr(iggy_module, "_PROM_HISTOGRAMS", {})
    monkeypatch.setattr(iggy_module, "PROMETHEUS_REGISTRY", registry)
    monkeypatch.setattr(iggy_module, "_MAKE_COUNTER", lambda *args, **kwargs: FakeCounter(*args, **kwargs))
    monkeypatch.setattr(iggy_module, "_MAKE_HISTOGRAM", lambda name, doc, labels: FakeHistogram(name, doc, labels, registry))

    class DummyClient:
        async def send(self, stream: str, topic: str, payload: Any, *, partition_strategy=None) -> None:
            return None

    metrics = iggy_module.IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda name, doc, labels: _StubHistogram(name, doc, labels))

    callback = IggyCallback(
        host='localhost',
        port=8090,
        transport='tcp',
        stream='cryptofeed',
        topic='trades',
        backend='iggy',
        client_factory=lambda host, port: DummyClient(),
        metrics=metrics,
    )

    await callback._emit({'exchange': 'BINANCE'})

    histogram = callback.metrics._histograms[("iggy_emit_latency_seconds", ("stream", "topic"))]
    assert histogram.samples[-1]['stream'] == 'cryptofeed'
    assert histogram.samples[-1]['topic'] == 'trades'
    assert histogram.samples[-1]['value'] >= 0


@pytest.mark.asyncio
async def test_iggy_emit_logs_success(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    class DummyClient:
        async def send(self, **kwargs: Any) -> None:
            return None

    metrics = iggy_module.IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        client_factory=lambda host, port: DummyClient(),
        metrics=metrics,
    )

    with caplog.at_level("INFO", logger="feedhandler.iggy"):
        await callback._emit({"exchange": "BINANCE"})

    message = "".join(caplog.messages)
    assert "event=emit_success" in message
    assert "stream=cryptofeed" in message
    assert "topic=trades" in message


@pytest.mark.asyncio
async def test_iggy_emit_logs_failure_and_metrics(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    import types
    from cryptofeed.backends import iggy as iggy_module
    from cryptofeed.backends.iggy import IggyCallback

    class FailingClient:
        async def send(self, **kwargs: Any) -> None:
            raise RuntimeError("boom")

    class FakeCounter:
        def __init__(self, *args, **kwargs) -> None:
            self.samples: list[dict[str, Any]] = []

        def labels(self, **labels: Any) -> "FakeCounter":
            self.samples.append(labels)
            return self

        def inc(self, amount: float = 1.0) -> None:
            if self.samples:
                self.samples[-1]['_amount'] = amount

    class FakeHistogram:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def labels(self, **labels: Any):
            return types.SimpleNamespace(observe=lambda value: None)

    registry: dict[str, Any] = {}
    monkeypatch.setattr(iggy_module, "_PROM_COUNTERS", {})
    monkeypatch.setattr(iggy_module, "_PROM_HISTOGRAMS", {})
    monkeypatch.setattr(iggy_module, "PROMETHEUS_REGISTRY", registry)
    monkeypatch.setattr(iggy_module, "_MAKE_COUNTER", lambda name, doc, labels: FakeCounter(name, doc, labels, registry))
    monkeypatch.setattr(iggy_module, "_MAKE_HISTOGRAM", lambda name, doc, labels: FakeHistogram(name, doc, labels, registry))

    metrics = iggy_module.IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))

    callback = IggyCallback(
        host="localhost",
        port=8090,
        transport="tcp",
        stream="cryptofeed",
        topic="trades",
        backend="iggy",
        retry_attempts=1,
        client_factory=lambda host, port: FailingClient(),
        metrics=metrics,
    )

    with caplog.at_level("ERROR", logger="feedhandler.iggy"):
        with pytest.raises(RuntimeError):
            await callback._emit({"exchange": "BINANCE"})

    message = "".join(caplog.messages)
    assert "event=emit_failure" in message
    assert "error=RuntimeError" in message
    counter = callback.metrics._counters[("iggy_emit_failure_total", ("error", "stream", "topic"))]
    assert counter.samples[-1]["stream"] == "cryptofeed"
    assert counter.samples[-1]["error"] == "RuntimeError"


def test_iggy_config_docs_reference_logging() -> None:
    doc_path = Path('docs/iggy_backend.md')
    content = doc_path.read_text()
    assert 'emit_success' in content
    assert 'iggy_emit_failure_total' in content


def test_config_docs_mentions_metrics() -> None:
    content = Path('docs/config.md').read_text()
    assert "iggy_emit_total" in content


def test_config_example_shows_retry() -> None:
    yaml_block = Path('docs/config.md').read_text()
    assert 'retry_attempts' in yaml_block
    assert 'prometheus_metrics' in yaml_block


def test_changelog_mentions_iggy() -> None:
    changelog = Path('CHANGES.md').read_text()
    assert 'Iggy backend' in changelog


def test_config_example_logging_metrics() -> None:
    config_doc = Path('docs/config.md').read_text()
    assert 'prometheus_metrics: true' in config_doc


def test_changelog_lists_metrics_logging() -> None:
    changelog = Path('CHANGES.md').read_text()
    assert 'emit_success' in changelog
    assert 'iggy_emit_latency_seconds' in changelog


def test_prometheus_registry_exposed() -> None:
    from cryptofeed.backends.iggy import IggyCallback, PROMETHEUS_REGISTRY

    class DummyClient:
        async def send(self, **kwargs):
            return None

    callback = IggyCallback(
        host='localhost',
        port=8090,
        transport='tcp',
        stream='cryptofeed',
        topic='trades',
        backend='iggy',
        client_factory=lambda host, port: DummyClient(),
    )

    assert PROMETHEUS_REGISTRY is not None


class _StubCounter:
    def __init__(self, name: str, doc: str, labelnames: tuple[str, ...], registry=None) -> None:
        self.samples = []
        self.labelnames = labelnames

    def labels(self, **labels: Any) -> "_StubCounter":
        self.samples.append(labels)
        return self

    def inc(self, amount: float = 1.0) -> None:
        if self.samples:
            self.samples[-1]['_amount'] = self.samples[-1].get('_amount', 0.0) + amount


class _StubHistogram:
    def __init__(self, name: str, doc: str, labelnames: tuple[str, ...], registry=None) -> None:
        self.samples = []
        self.labelnames = labelnames

    def labels(self, **labels: Any) -> "_StubHistogram":
        self.samples.append(labels)
        return self

    def observe(self, value: float) -> None:
        if self.samples:
            self.samples[-1]['value'] = value


def test_iggy_metrics_helper_reuses_counter() -> None:
    from cryptofeed.backends.iggy import IggyMetrics

    metrics = IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))

    metrics.increment_emit_success(stream='cryptofeed', topic='trades')
    metrics.increment_emit_success(stream='cryptofeed', topic='trades')

    counter = metrics._counters[("iggy_emit_total", ("stream", "topic"))]
    assert len(counter.samples) == 2
    assert counter.samples[-1]['_amount'] == 1.0


def test_iggy_metrics_helper_records_latency() -> None:
    from cryptofeed.backends.iggy import IggyMetrics

    metrics = IggyMetrics(make_counter=lambda *a, **k: _StubCounter(*a, **k), make_histogram=lambda *a, **k: _StubHistogram(*a, **k))

    metrics.observe_latency(0.5, stream='cryptofeed', topic='trades')
    histogram = metrics._histograms[("iggy_emit_latency_seconds", ("stream", "topic"))]
    assert histogram.samples[-1]['value'] == 0.5


def test_docs_mention_iggy_docker_tests() -> None:
    content = Path('docs/iggy_backend.md').read_text()
    assert 'IGGY_DOCKER_TESTS=1' in content
    assert 'pytest' in content
