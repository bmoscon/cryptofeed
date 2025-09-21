# Iggy Backend Requirements, Specifications, and Tasks

## Overview

Cryptofeed's Iggy backend mirrors the Kafka backend while keeping SOLID/KISS/DRY/YAGNI principles and consistent naming. `IggyTransport` owns client lifecycle (lazy connect, reuse per host/port). `IggyMetrics` centralises observability (Prometheus by default, optional OpenTelemetry). `IggyCallback` remains a thin queue consumer that delegates to those helpers.

## Functional Requirements

- Provide callback subclasses matching Kafka coverage: `TradeIggy`, `FundingIggy`, `BookIggy`, `TickerIggy`, `OpenInterestIggy`, `LiquidationsIggy`, `CandlesIggy`, `OrderInfoIggy`, `TransactionsIggy`, `BalancesIggy`, `FillsIggy`.
- Structured logging: `_emit` records `emit_success`, `emit_retry`, and `emit_failure` with retry metadata and exposes optional OTEL logger hooks.
- Metrics: expose counters `iggy_emit_total`, `iggy_emit_failure_total` and histogram `iggy_emit_latency_seconds`; exporters must be pluggable (Prometheus default, optional OTEL meter).
- Transport: `_default_client_factory(host=..., port=...)` plugs into `IggyTransport`; transports may support `tcp`, `http`, `quic`.

## Validation

- Docker end-to-end: `IGGY_DOCKER_TESTS=1 pytest tests/unit/test_iggy_backend.py tests/integration/test_iggy_backend.py -q`.
- Benchmarks: capture latency/throughput via `iggy_emit_latency_seconds` while replaying realistic loads.

## Documentation & Release

- Configuration (`docs/config.md`) shows retry/metrics toggles plus OTEL exporter notes.
- `CHANGES.md` documents structured logging, Prometheus/OTEL metrics, callback coverage, and Docker validation guidance.
