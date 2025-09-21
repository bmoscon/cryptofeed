# Iggy Backend Requirements, Specifications, and Tasks

## Overview

Cryptofeed's Iggy backend must mirror the Kafka backend architecture while keeping SOLID/KISS/DRY/YAGNI and consistent naming. `IggyTransport` owns client lifecycle, `IggyMetrics` centralises observability (Prometheus by default, optional OpenTelemetry), and `IggyCallback` remains a thin queue consumer that delegates to those helpers.

## Functional Requirements

- Provide callback subclasses for the same data types as Kafka: `TradeIggy`, `FundingIggy`, `BookIggy`, `TickerIggy`, `OpenInterestIggy`, `LiquidationsIggy`, `CandlesIggy`, `OrderInfoIggy`, `TransactionsIggy`, `BalancesIggy`, and `FillsIggy`. Naming must stay consistent (`<Name>Iggy`).
- Structured logging: `_emit` records `emit_success`, `emit_retry`, and `emit_failure` with retry metadata (attempts, duration, error type) and allows optional OpenTelemetry `LoggerProvider` hooks.
- Metrics: `IggyMetrics` exposes counters `iggy_emit_total`, `iggy_emit_failure_total` and histogram `iggy_emit_latency_seconds`; exporters must be pluggable (Prometheus fallback, optional OTEL Meter).
- Transport: `_default_client_factory(host=..., port=...)` plugs into `IggyTransport`; transports may support `tcp`, `http`, `quic` (consistent with Kafka multi-host support).

## Validation

- Docker end-to-end: `IGGY_DOCKER_TESTS=1 pytest tests/unit/test_iggy_backend.py tests/integration/test_iggy_backend.py -q`.
- Benchmarks: capture latency/throughput via `iggy_emit_latency_seconds` while replaying realistic loads for each callback type.

## Documentation & Release

- Configuration (`docs/config.md`) shows retry/metrics toggles and OTEL exporter notes.
- `CHANGES.md` documents structured logging, Prometheus/OTEL metrics, additional callback coverage, and Docker validation guidance.
