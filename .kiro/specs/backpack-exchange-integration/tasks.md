# Task Breakdown

## Phase 0 · Foundations & Feature Flag
- [x] **T0.1 Audit ccxt Backpack Usage** (`cryptofeed/exchanges/backpack_ccxt.py`, deployment configs)  
  Catalogue current dependencies on the ccxt adapter, note behavioural gaps, and draft a toggle plan for migration.
- [x] **T0.2 Introduce Feature Flag** (`cryptofeed/exchange/registry.py`, config loaders)  
  Add `backpack.native_enabled` option controlling whether FeedHandler instantiates native or ccxt-backed feeds.

## Phase 1 · Configuration & Symbols
- [x] **T1.1 Implement BackpackConfig** (`cryptofeed/config/backpack.py`)  
  Build Pydantic model enforcing ED25519 credential structure, sandbox endpoints, proxy overrides, and window bounds.
- [x] **T1.2 Build Symbol Service** (`cryptofeed/exchanges/backpack/symbols.py`)  
  Fetch `/api/v1/markets`, normalize symbols, detect instrument types, and cache results with TTL invalidation.
- [x] **T1.3 Wire Feed Bootstrap** (`cryptofeed/exchanges/backpack/feed.py`)  
  Integrate config + symbol service; expose helpers translating between normalized and native symbols.

## Phase 2 · Transports & Authentication
- [x] **T2.1 REST Client Wrapper** (`cryptofeed/exchanges/backpack/rest.py`)  
  Wrap `HTTPAsyncConn`, enforce Backpack endpoints, retries, circuit breaker, and snapshot helper APIs.
- [x] **T2.2 WebSocket Session Manager** (`cryptofeed/exchanges/backpack/ws.py`)  
  Wrap `WSAsyncConn`, add heartbeat watchdog, automatic resubscription, and proxy metadata propagation.
- [x] **T2.3 ED25519 Auth Mixin** (`cryptofeed/exchanges/backpack/auth.py`)  
  Validate keys, produce microsecond timestamps, sign payloads, and assemble REST/WS headers.
- [x] **T2.4 Private Channel Handshake** (`feed.py`, `ws.py`)  
  Combine auth mixin with WebSocket connect sequence and retry policy for auth failures.

## Phase 3 · Message Routing & Adapters
- [x] **T3.1 Router Skeleton** (`cryptofeed/exchanges/backpack/router.py`)  
  Dispatch envelopes to adapters, surface errors, and emit metrics for dropped frames.
- [x] **T3.2 Trade Adapter** (`cryptofeed/exchanges/backpack/adapters.py`)  
  Convert trade payloads to `Trade` dataclasses with decimal precision and sequence management.
- [x] **T3.3 Order Book Adapter** (`.../adapters.py`)  
  Manage snapshot + delta lifecycle, detect gaps, and trigger resync via REST snapshots.
- [x] **T3.4 Ancillary Channels** (`.../adapters.py`)  
  Implement ticker, candle, and private order/position adapters as scoped in design.

## Phase 4 · Feed Integration & Observability
- [x] **T4.1 Implement BackpackFeed** (`cryptofeed/exchanges/backpack/feed.py`)  
  Subclass `Feed`, bootstrap snapshots, manage stream loops, and register callbacks under feature flag guard.
- [x] **T4.2 Metrics & Logging** (`feed.py`, `router.py`)  
  Emit structured logs and counters for reconnects, auth failures, parser errors, message throughput.
- [x] **T4.3 Health Endpoint** (`cryptofeed/health/backpack.py`)  
  Report snapshot freshness, subscription status, and recent error counts for monitoring.
- [x] **T4.4 Exchange Registration** (`cryptofeed/defines.py`, `cryptofeed/exchanges/__init__.py`, docs)  
  Register `BACKPACK`, update discovery tables, and document feature flag availability.

## Phase 5 · Testing & Tooling
- [x] **T5.1 Unit Tests** (`tests/unit/test_backpack_*`)  
  Cover config validation, auth signatures (golden vectors), symbol normalization, router/adapters, and feed bootstrap.
- [x] **T5.2 Integration Tests** (`tests/integration/test_backpack_native.py`)  
  Validate REST snapshot + WS delta flow, proxy wiring, private channel handshake using fixtures/sandbox.
- [x] **T5.3 Fixture Library** (`tests/fixtures/backpack/`)  
  Record public/private payload samples, edge cases, and error frames for deterministic tests.
- [x] **T5.4 Credential Validator Tool** (`tools/backpack_auth_check.py`)  
  Provide CLI utility verifying ED25519 keys and timestamp drift for operators.

## Phase 6 · Documentation & Migration
- [x] **T6.1 Exchange Documentation Update** (`docs/exchanges/backpack.md`)  
  Document native feed configuration, auth setup, proxy examples, metrics, and observability story.
- [x] **T6.2 Migration Playbook** (`docs/runbooks/backpack_migration.md`)  
  Outline phased rollout, monitoring checkpoints, success/failure criteria, and rollback triggers.
- [x] **T6.3 Example Script** (`examples/backpack_native_demo.py`)  
  Demonstrate public + private subscriptions, logging, and error handling with feature flag enabled.
- [x] **T6.4 Deprecation Checklist** (`docs/migrations/backpack_ccxt.md`)  
  Track clean-up tasks for ccxt scaffolding once native feed reaches GA.

## Success Criteria
- Native feed achieves parity with ccxt path for trades and order book data while adding private channel support.
- ED25519 authentication consistently succeeds with accurate error reporting for invalid keys.
- Proxy-aware transports reuse existing infrastructure without regressing other exchanges.
- Automated tests (unit + integration) cover critical flows with deterministic fixtures running in CI.
- Operators can enable the feature flag, follow documentation, and monitor health signals during rollout.
