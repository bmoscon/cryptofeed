# Requirements Document

## Introduction
This test initiative verifies that cryptofeed’s proxy subsystem operates consistently across HTTP and WebSocket clients, covering both CCXT-backed feeds and native exchange implementations. The focus is on ensuring configuration precedence, protocol support, credential safety, and transport-specific behavior through automated test suites.

## Requirements

### Requirement 1: Configuration Precedence Coverage
**Objective:** As a QA engineer, I want automated tests to confirm environment, YAML, and programmatic proxy sources resolve correctly, so that deployments rely on deterministic precedence.

#### Acceptance Criteria
1. WHEN proxy settings are supplied via environment variables THEN the test harness SHALL assert they override YAML and programmatic defaults for both CCXT and native feeds.
2. WHEN proxy configuration exists only in YAML THEN the test suite SHALL verify HTTP and WebSocket clients inherit those values without requiring code changes.
3. WHEN programmatic `ProxySettings` are provided AND higher-precedence inputs are absent THEN the tests SHALL confirm the settings apply uniformly across client types.
4. IF multiple precedence levels conflict THEN the tests SHALL detect and report the effective configuration for audit purposes.

### Requirement 2: HTTP Client Proxy Validation
**Objective:** As a test lead, I want coverage that HTTP clients respect proxy settings for various exchanges, so that REST transports operate through required routes.

#### Acceptance Criteria
1. WHEN an exchange-specific HTTP proxy is defined THEN the tests SHALL assert `HTTPAsyncConn` uses the correct proxy URL for CCXT and native exchanges.
2. WHEN only global defaults are defined THEN the tests SHALL confirm fallback behavior for HTTP clients without overrides.
3. WHILE executing sequential HTTP requests THE tests SHALL ensure a single proxy-configured session is reused to avoid redundant handshakes.
4. IF credentials are embedded in proxy URLs THEN the tests SHALL verify logs or diagnostics do not leak sensitive information.

### Requirement 3: WebSocket Client Proxy Validation
**Objective:** As a reliability engineer, I want automated checks for WebSocket proxy behavior, so that streaming connections function under SOCKS and HTTP proxies.

#### Acceptance Criteria
1. WHEN SOCKS4 or SOCKS5 proxies are configured THEN the tests SHALL confirm CCXT and native WebSocket clients negotiate through `python-socks` parameters.
2. IF `python-socks` is unavailable THEN the suite SHALL assert the system raises the documented ImportError before attempting a connection.
3. WHEN HTTP/HTTPS proxies are used for WebSockets THEN the tests SHALL verify required headers (e.g., `Proxy-Connection`) are injected while preserving existing handshake arguments.
4. WHEN no WebSocket proxy is configured THEN the suite SHALL confirm direct connections proceed without proxy artifacts.

### Requirement 4: End-to-End Feed Integration
**Objective:** As a platform owner, I want end-to-end scenarios demonstrating proxy usage across CCXT and native feeds, so that production deployments have confidence in real-world behavior.

#### Acceptance Criteria
1. WHEN a CCXT feed (e.g., Backpack) runs under proxy-enabled settings THEN the tests SHALL assert trades or book snapshots route through the configured proxies.
2. WHEN a native feed (e.g., Binance WS) runs with proxy overrides THEN the suite SHALL confirm both HTTP metadata calls and WebSocket streams respect the proxy configuration.
3. WHERE mixed proxy configurations are defined (global defaults plus per-exchange overrides) THE tests SHALL validate each feed observes its intended route.
4. WHEN proxy settings are disabled globally THEN the tests SHALL verify feeds revert to direct connectivity without residual proxy side effects.
