# Iggy Backend Requirements, Specifications, and Tasks

## Overview

The Iggy backend mirrors Kafka's structure while keeping SOLID/KISS/DRY/YAGNI principles. `IggyTransport` manages client lifecycle (lazy connect, reuse per host/port); `IggyMetrics` centralises observability (Prometheus by default, optional OpenTelemetry). `IggyCallback` remains thin—queue handling plus structured logging.

## Functional Requirements

- Structured logging: `_emit` must record `emit_success`, `emit_retry`, and `emit_failure` events with retry metadata.
- Metrics: expose counters `iggy_emit_total`, `iggy_emit_failure_total` and histogram `iggy_emit_latency_seconds`, using Prometheus when available and fallback instruments otherwise; OTEL hooks may be supplied.
- Transport: `_default_client_factory(host=..., port=...)` wires into `IggyTransport`.

## Validation

- Docker end-to-end: `IGGY_DOCKER_TESTS=1 pytest tests/unit/test_iggy_backend.py tests/integration/test_iggy_backend.py -q`.
- Benchmarks: capture latency/throughput via `iggy_emit_latency_seconds` while replaying realistic loads.

## Documentation & Release

- Configuration (`docs/config.md`) shows retry/metrics toggles and OTEL notes.
- `CHANGES.md` documents structured logging, Prometheus/OTEL metrics, and Docker validation guidance.
