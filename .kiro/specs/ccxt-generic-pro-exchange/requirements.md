# Requirements Document

## Introduction
The CCXT/CCXT-Pro generic exchange abstraction aims to provide a consistent integration layer for all CCXT-backed exchanges. The focus is on standardizing configuration, transport usage (HTTP & WebSocket), and callback behavior so derived exchange implementations can be thin wrappers.

## Requirements

### Requirement 1: Unified Configuration
**Objective:** As a platform engineer, I want a single CCXT config surface for exchanges, so that onboarding new CCXT feeds is frictionless.

#### Acceptance Criteria
1. WHEN a CCXT exchange module loads THEN the generic layer SHALL expose standardized fields (API keys, proxies, timeouts) via Pydantic models.
2. IF exchange-specific options exist (rate limits, sandbox flags) THEN the generic layer SHALL provide extension hooks without modifying core configuration.
3. WHEN configuration is invalid THEN the system SHALL raise descriptive errors before initializing CCXT clients.

### Requirement 2: Transport Abstraction
**Objective:** As a feed developer, I want HTTP and WebSocket interactions routed through reusable transports, so that CCXT exchanges inherit proxy/logging behavior.

#### Acceptance Criteria
1. WHEN CCXT REST requests are issued THEN they SHALL use a shared `CcxtRestTransport` honoring proxy, retry, and logging policies.
2. WHEN CCXT WebSocket streams start THEN they SHALL use a shared `CcxtWsTransport` that integrates with the proxy system and metrics.
3. IF the underlying exchange lacks WebSocket support THEN the abstraction SHALL fall back to REST-only mode without errors.

### Requirement 3: Callback Normalization
**Objective:** As a downstream consumer, I want trade/order book callbacks to emit normalized cryptofeed objects, so that pipelines remain consistent across exchanges.

#### Acceptance Criteria
1. WHEN CCXT emits trades/books THEN the generic layer SHALL convert raw data into cryptofeed’s `Trade`/`OrderBook` structures using shared adapters.
2. IF fields are missing or null THEN defaults SHALL be applied or the event rejected with logging.
3. WHEN data passes through the generic layer THEN sequence numbers and timestamps SHALL be preserved for gap detection.

### Requirement 4: Test Coverage and Documentation
**Objective:** As a maintainer, I want comprehensive tests and docs for the generic layer, so that future exchanges can rely on stable behavior.

#### Acceptance Criteria
1. WHEN unit tests run THEN they SHALL cover configuration validation, transport behavior, and data normalization utilities.
2. WHEN integration tests execute THEN they SHALL verify a sample CCXT exchange uses proxy-aware transports and emits normalized callbacks.
3. WHEN documentation is updated THEN onboarding guides SHALL explain how to add new CCXT exchanges using the abstraction.
