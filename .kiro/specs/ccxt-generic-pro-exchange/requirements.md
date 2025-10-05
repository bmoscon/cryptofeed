# Requirements Document

## Introduction
Refactor the CCXT/CCXT-Pro abstraction so it adheres to Cryptofeed’s updated engineering principles—FRs over NFRs, conventional commits, and proxy-first architecture—while simplifying onboarding for derived CCXT exchanges. Delivery must prioritize functional parity first, then layer in observability and resilience iteratively.

## Requirements

### Requirement 1: Unified Configuration Surface (FR-first)
**Objective:** As a platform engineer, I want a single ccxt config surface aligned with FR-first delivery, so that onboarding new CCXT feeds is frictionless before we optimize non-functional concerns.

#### Acceptance Criteria
1. WHEN a CCXT exchange module loads THEN the generic layer SHALL expose standardized fields (API keys, proxies, timeouts) via Pydantic models consistent with SOLID/KISS.
2. IF exchange-specific options exist (rate limits, sandbox flags) THEN extension hooks SHALL ship as functional toggles, deferring NFR tuning to later iterations.
3. WHEN configuration is invalid THEN the system SHALL raise descriptive errors before initializing CCXT clients, with commit guidance following conventional commit prefixes.

### Requirement 2: Transport Abstraction & Proxy Alignment
**Objective:** As a feed developer, I want HTTP and WebSocket interactions routed through reusable transports that reuse the proxy system, so ccxt exchanges inherit consistent behavior without bespoke code.

#### Acceptance Criteria
1. WHEN CCXT REST requests are issued THEN they SHALL use a shared `CcxtRestTransport` honoring proxy, retry, and logging policies.
2. WHEN CCXT WebSocket streams start THEN they SHALL use shared transports that integrate with the proxy subsystem and surface FR metrics; NFR telemetry can iterate later.
3. IF the underlying exchange lacks WebSocket support THEN the abstraction SHALL fall back to REST-only mode without errors and log a conventional `warn` entry referencing fallback behavior.

### Requirement 3: Callback Normalization & Hooks
**Objective:** As a downstream consumer, I want trade/order book callbacks to emit normalized cryptofeed objects with explicit hook points, so pipelines remain consistent across exchanges.

#### Acceptance Criteria
1. WHEN CCXT emits trades/books THEN the generic layer SHALL convert raw data into cryptofeed’s `Trade`/`OrderBook` structures using shared adapters.
2. IF fields are missing or null THEN defaults SHALL be applied or the event rejected with logging that references the triggering spec requirement (FR-first traceability).
3. WHEN data passes through the generic layer THEN sequence numbers and timestamps SHALL be preserved for gap detection, with extension hooks for symbol/price/timestamp normalization.

### Requirement 4: Iterative Coverage & Documentation
**Objective:** As a maintainer, I want comprehensive tests and docs that follow FR-first delivery—functional coverage first, then non-functional hardening—so future exchanges can rely on stable behavior.

#### Acceptance Criteria
1. WHEN unit tests run THEN they SHALL cover configuration validation, transport behavior, and data normalization utilities before introducing performance/resiliency tests.
2. WHEN integration tests execute THEN they SHALL verify feed lifecycle with proxy-injected transports and private-channel guards using patched CCXT clients.
3. WHEN documentation is updated THEN onboarding guides SHALL follow conventional commit examples and describe the FR→NFR iteration plan.

### Requirement 5: Directory Organization & Change Hygiene
**Objective:** As a codebase maintainer, I want all ccxt-related modules grouped under a dedicated package with change hygiene that reflects conventional commits, so navigation and future extensions remain predictable.

#### Acceptance Criteria
1. WHEN developers inspect the source tree THEN all CCXT modules (config, transports, adapters, feeds, builder) SHALL reside beneath a common `cryptofeed/exchanges/ccxt/` directory hierarchy.
2. IF new CCXT components are introduced THEN they SHALL live inside the dedicated `ccxt` package, and commits SHALL use `feat:` / `refactor:` prefixes describing the change.
3. WHEN existing CCXT imports are updated THEN the refactor SHALL avoid breaking public APIs; temporary re-export shims MUST exist only as migration helpers documented with timelines for removal.
4. WHEN compatibility shims route to the new package THEN accompanying documentation SHALL call out the canonical import surface so downstream teams can migrate without ambiguity.
5. WHEN a shim becomes redundant THEN it SHALL be removed promptly (NO LEGACY principle) once downstream code has migrated, and the changelog SHALL record the removal under the relevant spec/task.
