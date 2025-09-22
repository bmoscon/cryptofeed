# Design Document

## Overview
The cryptofeed proxy system is an **extension** to the existing feed infrastructure. It injects HTTP and WebSocket proxy routing through declarative configuration without requiring exchange-specific code changes. The current MVP wires a global `ProxyInjector` into `HTTPAsyncConn` and `WSAsyncConn`, resolving per-exchange overrides from `ProxySettings`. This design preserves backward compatibility for deployments that do not opt in while providing deterministic proxy behavior when enabled.

## Context and Constraints
- **Technology Stack:** Python 3.11+, Pydantic v2, `aiohttp`, `websockets`, optional `python-socks` for SOCKS support.
- **Configuration Surface:** Environment variables, YAML, or programmatic instantiation using `ProxySettings`. Environment variables use the `CRYPTOFEED_PROXY_` prefix with double-underscore nesting.
- **Operational Constraints:** Existing feeds and adapters must continue to function without modification when proxying is disabled. Proxy routing cannot introduce additional connection setup steps in calling code.
- **Dependency Boundaries:** No new third-party services; optional dependencies must fail fast with actionable messaging.

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| R1.1–R1.4 | Global `ProxySettings` lifecycle and `init_proxy_system` initialization |
| R2.1–R2.4 | `HTTPAsyncConn` session creation using injector-resolved proxy URLs |
| R3.1–R3.4 | `ProxyInjector.create_websocket_connection` delegation logic |
| R4.1–R4.4 | `ProxyConfig` validation and inheritance semantics for defaults vs overrides |

## Architecture
The proxy system introduces a single injection point that every network connection reuses. No feed-specific code is aware of proxy logic.

```mermaid
graph TD
    OperatorConfig[Operator Configuration<br/>(env / YAML / code)] --> ProxySettings
    ProxySettings --> init_proxy_system
    init_proxy_system --> ProxyInjector
    ProxyInjector --> HTTPAsyncConn
    ProxyInjector --> WSAsyncConn
    HTTPAsyncConn -->|aiohttp.ClientSession| ExchangeREST
    WSAsyncConn -->|websockets.connect| ExchangeWebSocket
```

## Component Design
### ProxySettings
- Extends `BaseSettings` to hydrate configuration from environment variables or dictionaries.
- Exposes boolean `enabled`, optional `default` connection proxies, and per-exchange overrides keyed by exchange identifier.
- `get_proxy(exchange_id, connection_type)` resolves in priority order: disabled → exchange override → default → none.

### ConnectionProxies and ProxyConfig
- `ConnectionProxies` encapsulates optional HTTP and WebSocket `ProxyConfig` instances.
- `ProxyConfig` validates scheme, hostname, port, and timeout range during construction, guaranteeing invalid URIs fail before runtime.
- Accessor properties (`scheme`, `host`, `port`) expose parsed values for downstream consumers without repeated parsing.

### init_proxy_system and get_proxy_injector
- `init_proxy_system` instantiates a singleton `ProxyInjector` when `ProxySettings.enabled` is true; otherwise it clears the injector reference to ensure legacy direct connections.
- `get_proxy_injector` allows connection classes to retrieve the injector without importing configuration modules, keeping dependencies acyclic.

### ProxyInjector
- Centralizes proxy resolution. HTTP callers use `get_http_proxy_url(exchange_id)` to retrieve the raw URL for session construction.
- `create_websocket_connection` inspects proxy scheme:
  - For `socks4`/`socks5`, converts to `python-socks` enum and forwards parameters to `websockets.connect`.
  - For `http`/`https`, injects a `Proxy-Connection: keep-alive` header and otherwise reuses the original connection parameters.
  - Falls back to direct `websockets.connect` when no proxy is configured.
- `apply_http_proxy` remains a no-op placeholder to retain compatibility with earlier injection points; all functional logic resides in session creation.

### HTTPAsyncConn Integration
- On `_open`, retrieves a proxy URL via injector before initializing `aiohttp.ClientSession`.
- Fallback order: injector-resolved proxy → legacy `proxy` argument → none.
- Maintains the existing session reuse contract so repeated requests reuse the same client session with the chosen proxy configuration.

### WSAsyncConn Integration
- During `_open`, resolves the proxy via injector and delegates connection establishment to `ProxyInjector.create_websocket_connection`.
- Maintains compatibility with authentication hooks and callback instrumentation by preserving the original handshake flow when proxying is disabled.

### CCXT Feed Alignment
- CCXT-backed feeds (`CcxtFeed`) depend on `HTTPAsyncConn` and `WSAsyncConn`. No CCXT-specific changes are required; once connections use the injector, CCXT feeds inherit proxy behavior automatically.

## Control Flows
### Initialization and HTTP Request Flow
```mermaid
graph LR
    Start[Process Start] --> LoadConfig[Load ProxySettings]
    LoadConfig --> Enabled{settings.enabled?}
    Enabled -- No --> DirectTraffic[HTTPAsyncConn uses direct session]
    Enabled -- Yes --> init_proxy_system
    init_proxy_system --> HTTPOpen[HTTPAsyncConn._open]
    HTTPOpen --> ResolveHTTP[ProxyInjector.get_http_proxy_url]
    ResolveHTTP -->|Proxy found| SessionWithProxy[aiohttp.ClientSession(proxy=url)]
    ResolveHTTP -->|Proxy missing| LegacyFallback[Use legacy proxy argument]
    LegacyFallback --> SessionWithProxy
    ResolveHTTP -->|None| DirectSession[aiohttp.ClientSession()] 
```

### WebSocket Connection Flow
```mermaid
graph TD
    WSOpen[WSAsyncConn._open] --> ResolveWS[ProxyInjector.get_proxy(exchange,"websocket")]
    ResolveWS -->|SOCKS proxy| SockSetup[python-socks parameters]
    SockSetup --> WSConnect[websockets.connect]
    ResolveWS -->|HTTP proxy| HttpHeader[Inject Proxy-Connection header]
    HttpHeader --> WSConnect
    ResolveWS -->|None configured| DirectConnect[websockets.connect]
    WSConnect --> ActiveStream[Active WebSocket Session]
    DirectConnect --> ActiveStream
```

## Data and Configuration Model
- **Config Keys:** `enabled`, `default.http`, `default.websocket`, `exchanges.<id>.http`, `exchanges.<id>.websocket`.
- **Environment Variable Mapping:** Double underscore (`__`) expands nested structure (e.g., `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL`).
- **Programmatic Use:** Operators can instantiate `ProxySettings` from a Python dictionary or YAML payload and pass it to `init_proxy_system` before starting feeds.
- **Timeout Handling:** `ProxyConfig.timeout_seconds` is stored for future enhancements but does not alter `aiohttp` or `websockets` timeouts in the MVP.

## Error Handling
- Validation errors from `ProxyConfig` surface immediately during configuration loading to prevent runtime misconfiguration.
- Missing `python-socks` dependency throws an explicit `ImportError` with installation guidance.
- WebSocket handshake failures propagate through existing connection error paths while including proxy host/port in log entries for observability.
- Legacy `proxy` arguments remain supported, ensuring historical deployments do not fail when the injector returns `None`.

## Security and Observability
- Credentials embedded in proxy URLs remain confined to configuration sources; no additional logging of full URLs should be introduced.
- Recommend logging exchange ID, transport type, and proxy scheme (not full URL) upon initialization for audit trails.
- Integration with existing metrics hooks (`raw_data_callback`) remains unchanged; future work can add counters for proxy usage per exchange.

## Performance and Scalability Considerations
- Reuse of `aiohttp.ClientSession` per connection avoids redundant TCP handshakes when proxies are enabled.
- Proxy resolution occurs once per connection open, keeping the critical path minimal.
- Additional latency introduced by proxy routing is dominated by network hops; no extra application-layer processing is added.

## Testing Strategy
- **Unit Tests:**
  - Validate `ProxyConfig` parsing for supported and unsupported schemes.
  - Confirm `ProxySettings.get_proxy` override and fallback ordering.
  - Assert `ProxyInjector` SOCKS and HTTP branches invoke `websockets.connect` with correct parameters.
- **Integration Tests:**
  - Exercise `HTTPAsyncConn` and `WSAsyncConn` with injector initialized to verify sessions are created and torn down under proxy settings.
  - Cover legacy behavior by disabling the injector and ensuring direct connections still succeed.
- **Configuration Tests:**
  - Load settings from environment variable fixtures to ensure double-underscore parsing works for nested overrides.
- **Dependency Tests:**
  - Simulate missing `python-socks` to validate the error path and message clarity.

## Risks and Mitigations
- **Optional Dependency Drift:** If `python-socks` versions change, regression tests should assert compatibility; document required version ranges.
- **Credential Leakage:** Ensure logs never print full proxy URLs; add targeted tests if logging is expanded.
- **Timeout Semantics:** Because `timeout_seconds` is not yet applied, deployments may assume enforcement. Documentation must clarify current behavior and future roadmap.

## Future Enhancements
- Apply `timeout_seconds` to `aiohttp` and WebSocket clients once validated.
- Surface proxy usage metrics via the existing metrics subsystem.
- Introduce per-exchange circuit breaker or retry policies informed by proxy-specific failure modes.
- Expand support for authenticated HTTP proxies via header injection when required by upstream infrastructure.
