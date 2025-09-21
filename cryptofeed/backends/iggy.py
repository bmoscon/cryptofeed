"""Apache Iggy backend scaffolding.

Incrementally implemented via TDD; this file currently exposes configuration,
key semantics, and book snapshot bookkeeping.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

SUPPORTED_TRANSPORTS = {"tcp", "http", "quic"}
SUPPORTED_SERIALIZERS = {"json", "binary"}

from cryptofeed.backends.backend import BackendCallback, BackendBookCallback, BackendQueue


class _FallbackCounter:
    def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...], registry: Any) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self.registry = registry
        self.samples: list[dict[str, Any]] = []

    def labels(self, **labels: Any) -> "_FallbackCounter":
        self.samples.append(labels)
        return self

    def inc(self, amount: float = 1.0) -> None:
        if self.samples:
            self.samples[-1]["_amount"] = self.samples[-1].get("_amount", 0.0) + amount


class _FallbackHistogram:
    def __init__(self, name: str, documentation: str, labelnames: tuple[str, ...], registry: Any) -> None:
        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self.registry = registry
        self.samples: list[dict[str, Any]] = []

    def labels(self, **labels: Any) -> "_FallbackHistogram":
        entry = dict(labels)
        self.samples.append(entry)
        return self

    def observe(self, value: float) -> None:
        if self.samples:
            self.samples[-1]["value"] = value


class _FallbackRegistry(dict):
    """Minimal placeholder registry when prometheus_client is unavailable."""


def _load_prometheus() -> tuple[Any, Callable[[str, str, tuple[str, ...]], Any], Callable[[str, str, tuple[str, ...]], Any]]:
    try:
        module = importlib.import_module("prometheus_client")
    except ModuleNotFoundError:
        registry = _FallbackRegistry()

        def make_counter(name: str, documentation: str, labelnames: tuple[str, ...]) -> _FallbackCounter:
            return _FallbackCounter(name, documentation, labelnames, registry)

        def make_histogram(name: str, documentation: str, labelnames: tuple[str, ...]) -> _FallbackHistogram:
            return _FallbackHistogram(name, documentation, labelnames, registry)

        return registry, make_counter, make_histogram

    registry = module.CollectorRegistry()

    def make_counter(name: str, documentation: str, labelnames: tuple[str, ...]) -> Any:
        return module.Counter(name, documentation, labelnames=labelnames, registry=registry)

    def make_histogram(name: str, documentation: str, labelnames: tuple[str, ...]) -> Any:
        return module.Histogram(name, documentation, labelnames=labelnames, registry=registry)

    return registry, make_counter, make_histogram


PROMETHEUS_REGISTRY, _MAKE_COUNTER, _MAKE_HISTOGRAM = _load_prometheus()


class IggyTransport:
    """Lazy wrapper around the underlying iggy client."""

    def __init__(self, *, host: str, port: int, client_factory: Callable[..., Any]) -> None:
        self._host = host
        self._port = port
        self._factory = client_factory
        self._client: Any = None

    def client(self) -> Any:
        if self._client is None:
            client = self._factory(host=self._host, port=self._port)
            if client is None:
                raise RuntimeError("Iggy client factory returned None")
            self._client = client
        return self._client


class IggyMetrics:
    """Collects counters and histograms for Iggy backend events."""

    def __init__(
        self,
        *,
        registry: Any = PROMETHEUS_REGISTRY,
        make_counter: Callable[[str, str, tuple[str, ...]], Any] = _MAKE_COUNTER,
        make_histogram: Callable[[str, str, tuple[str, ...]], Any] = _MAKE_HISTOGRAM,
    ) -> None:
        self.registry = registry
        self._make_counter = make_counter
        self._make_histogram = make_histogram
        self._counters: dict[tuple[str, tuple[str, ...]], Any] = {}
        self._histograms: dict[tuple[str, tuple[str, ...]], Any] = {}

    def increment_emit_success(self, **labels: Any) -> None:
        self._counter("iggy_emit_total", labels).labels(**labels).inc()

    def increment_emit_failure(self, **labels: Any) -> None:
        self._counter("iggy_emit_failure_total", labels).labels(**labels).inc()

    def observe_latency(self, duration: float, **labels: Any) -> None:
        self._histogram(
            "iggy_emit_latency_seconds",
            "Iggy emit latency",
            labels,
        ).labels(**labels).observe(duration)

    def _counter(self, name: str, labels: dict[str, Any]) -> Any:
        labelnames = tuple(sorted(labels.keys()))
        key = (name, labelnames)
        counter = self._counters.get(key)
        if counter is None:
            counter = self._make_counter(name, f"Iggy backend metric {name}", labelnames)
            self._counters[key] = counter
        return counter

    def _histogram(self, name: str, documentation: str, labels: dict[str, Any]) -> Any:
        labelnames = tuple(sorted(labels.keys()))
        key = (name, labelnames)
        histogram = self._histograms.get(key)
        if histogram is None:
            histogram = self._make_histogram(name, documentation, labelnames)
            self._histograms[key] = histogram
        return histogram


DEFAULT_IGGY_METRICS = IggyMetrics()
_PROM_COUNTERS: dict[str, Any] = {}
_PROM_HISTOGRAMS: dict[str, Any] = {}


def _default_client_factory(*, host: str, port: int) -> Any:
    try:
        from iggy.client import Client
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Install iggy-py to use the default Iggy backend client"
        ) from exc
    return Client(host=host, port=port)


LOG = logging.getLogger("feedhandler.iggy")


@dataclass(frozen=True, slots=True)
class IggyConfig:
    host: str
    port: int
    transport: str
    stream: str
    topic: str
    backend: str
    tls: bool = False
    auth: Optional[str] = None
    partition_strategy: Optional[str] = None
    serializer: str = "json"
    batch_size: int = 1
    flush_interval_ms: Optional[int] = None
    auto_create: bool = False
    retry_attempts: int = 3
    retry_backoff_ms: Sequence[int] | int = 100
    max_inflight: Optional[int] = None
    key: Optional[str] = None
    value_serializer: Optional[Callable[[dict[str, Any]], bytes]] = None


class IggyCallback(BackendQueue):
    """Base callback for emitting records into an Apache Iggy stream."""

    def start(self, loop, multiprocess: bool = False) -> None:
        """Start the background writer and mark the callback running."""
        self.running = True
        super().start(loop, multiprocess=multiprocess)

    def __init__(
        self,
        *,
        host: str,
        port: int,
        transport: str,
        stream: str,
        topic: str,
        backend: str,
        tls: bool = False,
        auth: Optional[str] = None,
        partition_strategy: Optional[str] = None,
        serializer: str = "json",
        batch_size: int = 1,
        flush_interval_ms: Optional[int] = None,
        auto_create: bool = False,
        retry_attempts: int = 3,
        retry_backoff_ms: Sequence[int] | int = 100,
        max_inflight: Optional[int] = None,
        key: Optional[str] = None,
        value_serializer: Optional[Callable[[dict[str, Any]], bytes]] = None,
        client_factory: Optional[Callable[["IggyCallback"], Any]] = None,
        metrics: Optional[IggyMetrics] = None,
        transport_adapter: Optional[IggyTransport] = None,
        numeric_type=float,
        none_to=None,
    ) -> None:
        if not host:
            raise ValueError("host must be provided")
        if not stream:
            raise ValueError("stream must be provided")
        if transport not in SUPPORTED_TRANSPORTS:
            raise ValueError("unsupported transport")
        if serializer not in SUPPORTED_SERIALIZERS:
            raise ValueError("unsupported serializer")
        default_key = getattr(self, "default_key", None)
        resolved_key = key or default_key or topic
        self.config = IggyConfig(
            host=host,
            port=port,
            transport=transport,
            stream=stream,
            topic=topic,
            backend=backend,
            tls=tls,
            auth=auth,
            partition_strategy=partition_strategy,
            serializer=serializer,
            batch_size=batch_size,
            flush_interval_ms=flush_interval_ms,
            auto_create=auto_create,
            retry_attempts=retry_attempts,
            retry_backoff_ms=retry_backoff_ms,
            max_inflight=max_inflight,
            key=resolved_key,
            value_serializer=value_serializer,
        )
        self.host = host
        self.port = port
        self.transport = transport
        self.stream = stream
        self.topic = topic
        self.backend = backend
        self.tls = tls
        self.auth = auth
        self.partition_strategy = partition_strategy
        self.serializer = serializer
        self.batch_size = batch_size
        self.flush_interval_ms = flush_interval_ms
        self.auto_create = auto_create
        self.retry_attempts = retry_attempts
        self.retry_backoff_ms = retry_backoff_ms
        self.max_inflight = max_inflight
        self.key = resolved_key
        self.value_serializer = value_serializer
        client_factory = client_factory or _default_client_factory
        self.transport = transport_adapter or IggyTransport(host=host, port=port, client_factory=client_factory)
        self.metrics = metrics or DEFAULT_IGGY_METRICS
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.running = False
        self.started = False

    def log_connection_event(self, event: str, level: int = logging.INFO, **info: Any) -> None:
        fields = {"event": event, "host": self.host, "stream": self.stream, "topic": self.topic}
        fields.update({k: v for k, v in info.items() if k != "auth"})
        message = "; ".join(f"{k}={v}" for k, v in fields.items())
        LOG.log(level, message)

    async def write(self, data):
        serialized = self._serialize(data)
        await super().write(serialized)

    async def _emit(self, payload):
        client = self.transport.client()
        attempts = 0
        start = time.perf_counter()
        while True:
            try:
                await client.send(
                    stream=self.stream,
                    topic=self.topic,
                    payload=payload,
                    partition_strategy=self.partition_strategy,
                )
            except Exception as exc:  # noqa: BLE001 - propagate unexpected failures after retries
                attempts += 1
                if attempts >= self.retry_attempts:
                    self.metrics.increment_emit_failure(stream=self.stream, topic=self.topic, error=exc.__class__.__name__)
                    self.log_connection_event("emit_failure", level=logging.ERROR, error=exc.__class__.__name__, retries=attempts)
                    raise
                self.log_connection_event("emit_retry", level=logging.WARNING, error=exc.__class__.__name__, attempt=attempts)
                await asyncio.sleep(self._retry_delay(attempts))
                continue
            break
        duration = time.perf_counter() - start
        self.metrics.increment_emit_success(stream=self.stream, topic=self.topic)
        self.metrics.observe_latency(duration, stream=self.stream, topic=self.topic)
        self.log_connection_event("emit_success", retries=attempts, duration_ms=round(duration * 1000, 3))


    def _retry_delay(self, attempt: int) -> float:
        backoff = self.retry_backoff_ms
        if isinstance(backoff, (tuple, list)):
            index = min(attempt - 1, len(backoff) - 1)
            return float(backoff[index]) / 1000
        return float(backoff) / 1000

    def _serialize(self, payload):
        if self.serializer == "json":
            return payload
        if self.serializer == "binary":
            if self.value_serializer is None:
                raise TypeError("binary serializer requires value_serializer")
            return self.value_serializer(payload)
        return payload

    async def writer(self) -> None:  # pragma: no cover - orchestration handled in tests
        try:
            while True:
                async with self.read_queue() as updates:
                    if not updates:
                        if not self.running:
                            break
                        continue
                    for update in updates:
                        await self._emit(update)
        finally:
            self.running = False


class TradeIggy(IggyCallback, BackendCallback):
    """Trade callback placeholder with Kafka-parity key semantics."""

    default_key = "trades"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class TickerIggy(IggyCallback, BackendCallback):
    """Ticker callback placeholder mirroring Kafka backend semantics."""

    default_key = "ticker"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class BookIggy(IggyCallback, BackendBookCallback):
    """Order book callback placeholder with snapshot support."""

    default_key = "book"

    def __init__(
        self,
        *args,
        snapshots_only: bool = False,
        snapshot_interval: int = 1000,
        **kwargs,
    ) -> None:
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class FundingIggy(IggyCallback, BackendCallback):
    default_key = "funding"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class OpenInterestIggy(IggyCallback, BackendCallback):
    default_key = "open_interest"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class LiquidationsIggy(IggyCallback, BackendCallback):
    default_key = "liquidations"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class CandlesIggy(IggyCallback, BackendCallback):
    default_key = "candles"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class OrderInfoIggy(IggyCallback, BackendCallback):
    default_key = "order_info"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class TransactionsIggy(IggyCallback, BackendCallback):
    default_key = "transactions"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class BalancesIggy(IggyCallback, BackendCallback):
    default_key = "balances"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class FillsIggy(IggyCallback, BackendCallback):
    default_key = "fills"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
