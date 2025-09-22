# Requirements Document

## Introduction
This specification captures the currently implemented Cryptofeed Proxy System MVP. The feature enables HTTP and WebSocket proxy routing without modifying exchange integrations by wiring a global `ProxyInjector` into existing connection classes. Operators configure behavior declaratively through Pydantic v2 `ProxySettings`, using environment variables, YAML, or code to define global defaults and per-exchange overrides across HTTP(S) and SOCKS proxies.

## Requirements

### Requirement 1: Proxy Activation and Default Resolution
**Objective:** As a DevOps engineer, I want deterministic activation and fallback behavior, so that enabling or disabling proxies is predictable across all exchanges.

#### Acceptance Criteria
1. WHEN `ProxySettings.enabled` is false THEN the Cryptofeed Proxy System SHALL return `None` for all HTTP and WebSocket proxy lookups, allowing direct network access.
2. WHEN `ProxySettings.enabled` is true AND no exchange override is defined THEN the Cryptofeed Proxy System SHALL return the `default` `ConnectionProxies` values for both HTTP and WebSocket requests.
3. WHEN environment variables prefixed `CRYPTOFEED_PROXY_` are supplied THEN the Cryptofeed Proxy System SHALL populate `ProxySettings` fields using the double-underscore nesting delimiter.
4. WHEN `init_proxy_system` is invoked with `ProxySettings.enabled` true THEN the Cryptofeed Proxy System SHALL expose a global `ProxyInjector` through `get_proxy_injector()` for downstream connections.

### Requirement 2: HTTP Transport Proxying
**Objective:** As a REST transport maintainer, I want HTTP connections to respect proxy configuration while preserving existing behavior, so that feeds continue functioning under new routing policies.

#### Acceptance Criteria
1. WHEN an `HTTPAsyncConn` opens AND `ProxyInjector` resolves an HTTP proxy THEN the system SHALL create an `aiohttp.ClientSession` using that proxy URL for subsequent requests.
2. IF `ProxyInjector` resolves no HTTP proxy for an exchange THEN the system SHALL create the `aiohttp.ClientSession` without altering the direct connection flow.
3. WHEN a legacy `proxy` argument is provided to `HTTPAsyncConn` AND `ProxyInjector` returns `None` THEN the system SHALL reuse the legacy proxy value for session creation.
4. WHILE an `HTTPAsyncConn` session remains open THE system SHALL reuse the same `aiohttp.ClientSession` instance for multiple requests.

### Requirement 3: WebSocket Transport Proxying
**Objective:** As a WebSocket integrator, I want SOCKS and HTTP proxy support implemented according to current dependencies, so that exchange streams can route through required infrastructure.

#### Acceptance Criteria
1. WHEN `ProxySettings` resolves a SOCKS4 or SOCKS5 proxy for an exchange THEN the Cryptofeed Proxy System SHALL require the `python-socks` dependency and pass the proxy host and port to `websockets.connect`.
2. IF `python-socks` is absent WHEN a SOCKS proxy is requested THEN the Cryptofeed Proxy System SHALL raise an `ImportError` instructing operators to install `python-socks`.
3. WHEN `ProxySettings` resolves an HTTP or HTTPS proxy for a WebSocket THEN the Cryptofeed Proxy System SHALL set the `Proxy-Connection` header to `keep-alive` while establishing the WebSocket session.
4. IF no WebSocket proxy is configured for an exchange THEN the Cryptofeed Proxy System SHALL call `websockets.connect` with the original connection arguments.

### Requirement 4: Configuration Validation and Fallback Semantics
**Objective:** As a platform owner, I want configuration errors caught early and overrides to behave predictably, so that deployments fail fast when misconfigured and inherit defaults when appropriate.

#### Acceptance Criteria
1. WHEN a `ProxyConfig` is instantiated without a scheme, hostname, or port THEN the Cryptofeed Proxy System SHALL raise a validation error before initialization completes.
2. WHEN a `ProxyConfig` includes a scheme outside `http`, `https`, `socks4`, or `socks5` THEN the Cryptofeed Proxy System SHALL reject the configuration prior to any network activity.
3. WHEN an exchange override omits HTTP or WebSocket settings THEN the Cryptofeed Proxy System SHALL inherit the corresponding values from the default `ConnectionProxies` when available.
4. IF a `ProxyConfig.timeout_seconds` value is provided THEN the Cryptofeed Proxy System SHALL retain the value in the configuration model without modifying asyncio client timeouts in the current MVP.
