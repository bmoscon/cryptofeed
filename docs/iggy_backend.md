# Iggy Backend Requirements, Specifications, and Tasks

## Overview

Cryptofeed's Iggy backend mirrors the Kafka backend while respecting SOLID/KISS/DRY/YAGNI with consistent naming. `IggyTransport` owns client lifecycle (lazy connect/reuse for `tcp`/`http`/`quic`); `IggyMetrics` centralises observability (Prometheus counters/histograms by default, optional OpenTelemetry exporters). `IggyCallback` remains a thin queue consumer with structured logging.

## Functional Requirements

- Provide callback subclasses matching Kafka coverage: `TradeIggy`, `FundingIggy`, `BookIggy`, `TickerIggy`, `OpenInterestIggy`, `LiquidationsIggy`, `CandlesIggy`, `OrderInfoIggy`, `TransactionsIggy`, `BalancesIggy`, `FillsIggy`.
- Book handling: `BookIggy` must honour snapshot interval/snapshots-only semantics identical to Kafka's `BookKafka`.
- Structured logging: `_emit` records `emit_success`, `emit_retry`, `emit_failure` with retry metadata and supports optional OTEL logger hooks.
- Metrics: expose counters `iggy_emit_total`, `iggy_emit_failure_total` and histogram `iggy_emit_latency_seconds`; OTEL `MeterProvider` may plug in via factories.
- Transport: `_default_client_factory(host=..., port=...)` plugs into `IggyTransport`; transports may support `tcp`, `http`, `quic` host lists similar to Kafka bootstrap.

## Validation

- Docker end-to-end: `IGGY_DOCKER_TESTS=1 pytest tests/unit/test_iggy_backend.py tests/integration/test_iggy_backend.py -q`.
- Benchmarks: capture latency/throughput via `iggy_emit_latency_seconds` while replaying realistic loads for all callback types.

## Documentation & Release

- Configuration (`docs/config.md`) shows retry/metrics toggles plus OTEL exporter notes.
- `CHANGES.md` documents structured logging, Prometheus/OTEL metrics, full callback coverage, and Docker validation guidance.
