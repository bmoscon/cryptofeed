# Iggy Backend Requirements, Specifications, and Tasks

## Overview

Cryptofeed's Iggy backend mirrors the Kafka backend while respecting SOLID/KISS/DRY/YAGNI principles and consistent naming. `IggyTransport` owns client lifecycle (lazy connect, reuse per host/port). `IggyMetrics` centralises observability (Prometheus by default, optional OpenTelemetry). `IggyCallback` stays thin—queue handling plus structured logging.

## Functional Requirements

- Provide callback subclasses matching Kafka coverage: `TradeIggy`, `FundingIggy`, `BookIggy`, `TickerIggy`, `OpenInterestIggy`, `LiquidationsIggy`, `CandlesIggy`, `OrderInfoIggy`, `TransactionsIggy`, `BalancesIggy`, `FillsIggy`.
- Book handling: `BookIggy` matches Kafka snapshot interval/snapshots-only semantics.
- Structured logging: `_emit` records `emit_success`, `emit_retry`, and `emit_failure` with retry metadata and supports optional OTEL logger hooks.
- Metrics: expose counters `iggy_emit_total`, `iggy_emit_failure_total` and histogram `iggy_emit_latency_seconds`; exporters must be pluggable (Prometheus default, optional OTEL meter).
- Transport: `_default_client_factory(host=..., port=...)` plugs into `IggyTransport`; transports may support `tcp`, `http`, `quic` host lists.
- Auto-provision: when `auto_create` is enabled, create missing streams, topics, and partitions before publishing by issuing the same `get_*`/`create_*` calls demonstrated in the Iggy Python examples so producers never fail on first write. citeturn1search1
- Authentication & configuration: expose username/password, personal access token, and transport scheme (HTTP/TCP/QUIC) as first-class config so the backend can mirror the example workflow of loading credentials from environment variables and instantiating the proper `IggyClient` implementation. citeturn1search1
- Partition strategy: allow callbacks to choose between partition-id pinning and key-based hashing to preserve ordering semantics, matching the example usage of `PollingStrategy::next()` and consumer-group builders. citeturn1search4
- Consumer semantics: document and validate consumer-group offset management so downstream consumers interoperating with our streams behave like the official consumer and consumer-group samples. citeturn1search0turn1search4
- Polling contract: enforce support for `poll_messages` with `PollingStrategy::next()`/`auto_commit` defaults, including batch sizing and poll interval controls reflected in the official SDK examples. citeturn1search0turn1search4
- Connection strings: accept full `iggy+<transport>://user:password@host:port` URIs so operators can reuse the CLI-style connection string emitted by upstream helpers. citeturn1search1

## Validation

- Docker end-to-end: `IGGY_DOCKER_TESTS=1 pytest tests/unit/test_iggy_backend.py tests/integration/test_iggy_backend.py -q`.
- Benchmarks: capture latency/throughput via `iggy_emit_latency_seconds` while replaying realistic loads.

## Documentation & Release

- Configuration (`docs/config.md`) shows retry/metrics toggles plus OTEL exporter notes.
- `CHANGES.md` documents structured logging, Prometheus/OTEL metrics, callback coverage, and Docker validation guidance.

## Gap Analysis vs Apache Iggy Python Examples (Aug 2025)

- Align quick-start docs with the official README by referencing producer, consumer, and consumer-group entry points so operators can run parity smoke tests against upstream samples. citeturn1search3
- Add a checklist to ensure environment management (`python-dotenv`), logging, and CLI ergonomics are covered when packaging the backend utilities, mirroring the `examples/python` README guidance. citeturn1search3
- Track follow-up work to exercise auto-provisioning and consumer-group behavior against a running Iggy server using the published scripts as acceptance tests. citeturn1search0turn1search3
