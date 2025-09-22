# Implementation Tasks

## Milestone 1: Configuration and Initialization
- [x] Expose `ProxySettings` initialization path in application startup (env, YAML, code) and call `init_proxy_system` before feeds start.
- [x] Document expected environment variable keys in configuration guides and ensure loading precedence (env → YAML → code) is tested.
- [x] Add guardrails to reset the global injector when proxy settings are disabled to avoid stale state between runs.

## Milestone 2: HTTP Transport Integration
- [x] Update `HTTPAsyncConn._open` to retrieve the global injector and apply exchange-specific proxy URLs before creating `aiohttp.ClientSession`.
- [x] Ensure legacy `proxy` argument remains as fallback when injector returns `None`, adding tests to cover both cases.
- [x] Confirm session reuse maintains proxy configuration across repeated REST requests, including retry paths.

## Milestone 3: WebSocket Transport Integration
- [x] Route WebSocket creation through `ProxyInjector.create_websocket_connection`, handling SOCKS and HTTP schemes per design.
- [x] Add error handling for missing `python-socks` dependency with clear user guidance and unit tests covering the failure path.
- [x] Verify `Proxy-Connection` header injection for HTTP proxies and ensure it does not leak to non-proxy connections.

## Milestone 4: Validation and Fallback Semantics
- [x] Extend tests covering `ProxyConfig` validation and inheritance rules for defaults vs exchange overrides.
- [x] Confirm `timeout_seconds` persists in configuration models while documenting that runtime clients ignore it in the MVP.
- [x] Add logging or metrics hooks that surface proxy scheme usage without exposing credentials.

## Milestone 5: Documentation and Deployment Readiness
- [x] Update user and technical documentation (`docs/proxy/*.md`, `docs/README.md`) to reflect configuration changes and dependency requirements.
- [x] Provide deployment examples covering Docker/Kubernetes environment variable setups and YAML configuration files.
- [x] Publish testing checklist ensuring unit, integration, and configuration tests run in CI with proxy scenarios enabled.
