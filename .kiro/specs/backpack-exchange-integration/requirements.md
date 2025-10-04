# Requirements Document

## Introduction
This specification defines the Backpack exchange integration after the legacy ccxt pathway has been removed. The goal is to keep the exchange stack clean, modern, and aligned with Cryptofeed engineering principles (SOLID, KISS, DRY, YAGNI) while explicitly rejecting any backwards-compatibility shims or deprecated code paths.

## Requirements

### Requirement 1: Native Feed Activation & Legacy Removal
**Objective:** As a platform engineer, I want Backpack to load exclusively through the native cryptofeed modules, so that no ccxt-era compatibility remains in production.

#### Acceptance Criteria
1. WHEN the FeedHandler registers Backpack THEN `BackpackFeed` SHALL resolve from `cryptofeed.exchanges.backpack` without importing `cryptofeed.exchanges.backpack_ccxt`.
2. IF any runtime configuration references `backpack_ccxt` THEN the ConfigLoader SHALL raise a descriptive error instructing operators to migrate to the native feed.
3. WHEN Backpack configuration is loaded without a `backpack.native_enabled` flag THEN the ConfigLoader SHALL default to the native feed with no compatibility toggles.

### Requirement 2: Configuration Validation & Simplicity
**Objective:** As a deployer, I want Backpack configuration to enforce modern contracts, so that only valid, minimal settings are accepted.

#### Acceptance Criteria
1. WHEN Backpack credentials are provided THEN `BackpackConfig` SHALL validate ED25519 keys, sandbox toggles, and proxy overrides using native Pydantic models.
2. IF private channels are enabled THEN `BackpackConfig` SHALL require ED25519 key material and passphrase data before finalizing the configuration.
3. WHEN unsupported or legacy configuration fields are supplied THEN `BackpackConfig` SHALL reject them with explicit guidance that no compatibility shims exist.

### Requirement 3: Transport & Proxy Integration
**Objective:** As an operator, I want Backpack REST and WebSocket transports to reuse the consolidated proxy system, so that network behavior remains consistent across exchanges.

#### Acceptance Criteria
1. WHEN `BackpackRestClient` issues REST requests THEN it SHALL route through `HTTPAsyncConn` using the resolved proxy (pool-aware when configured) for the exchange.
2. WHEN `BackpackWsSession` opens a WebSocket THEN it SHALL source proxy information from `ProxyInjector`, supporting HTTP/SOCKS pools without custom code.
3. IF a proxy pool entry becomes unhealthy THEN the proxy subsystem SHALL rotate to the next candidate without requiring Backpack-specific logic.

### Requirement 4: Market Data Normalization
**Objective:** As a downstream consumer, I want Backpack market data normalized exactly like other exchanges, so that pipelines stay uniform without compatibility hacks.

#### Acceptance Criteria
1. WHEN the symbol cache is hydrated THEN `BackpackSymbolService` SHALL expose normalized and native identifiers with instrument type metadata.
2. WHEN trade or order book payloads arrive THEN `BackpackMessageRouter` SHALL produce cryptofeed `Trade` and `OrderBook` objects using Decimal precision and sequence tracking.
3. IF malformed data is detected THEN the router SHALL log structured warnings and drop the event without introducing fallback parsing paths.

### Requirement 5: ED25519 Authentication & Security
**Objective:** As an authenticated user, I want private channel access secured with Backpack’s ED25519 scheme, so that signatures remain accurate without legacy helpers.

#### Acceptance Criteria
1. WHEN private channel subscriptions are requested THEN `BackpackAuthHelper` SHALL generate Base64-encoded ED25519 signatures using microsecond timestamps.
2. IF signature verification fails THEN the WebSocket session SHALL surface actionable errors describing ED25519 format and window requirements.
3. WHILE private sessions remain active THE Backpack integration SHALL rotate timestamps within the configured window to prevent replay without falling back to deprecated auth modes.

### Requirement 6: Observability, Testing & Documentation
**Objective:** As a maintainer, I want complete coverage for Backpack’s native implementation, so that regression detection and knowledge transfer stay reliable.

#### Acceptance Criteria
1. WHEN the automated test suite runs THEN it SHALL include unit and integration tests covering configuration, symbol discovery, transports, authentication, and router behavior without mocks.
2. WHEN operator documentation is published THEN `docs/exchanges/backpack.md` SHALL describe native-only setup, proxy usage, health checks, and the removal of ccxt fallback.
3. WHEN operational runbooks are reviewed THEN `docs/runbooks/backpack_migration.md` SHALL confirm the ccxt path is decommissioned and outline monitoring for the native feed.
