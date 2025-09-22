# Design Document

## Overview
The cryptofeed proxy system is an **extension** to the existing feed infrastructure following engineering principles of START SMALL, SOLID, KISS, and YAGNI. It injects HTTP and WebSocket proxy routing through declarative configuration without requiring exchange-specific code changes.

## Context and Constraints
- **Technology Stack**: Python 3.11+, Pydantic v2, aiohttp, websockets, optional python-socks
- **Configuration Surface**: Environment variables, YAML, or programmatic instantiation
- **Operational Constraints**: Existing feeds must continue functioning without modification
- **Dependency Boundaries**: No new third-party services; optional dependencies fail fast

## Architecture Overview

Simple 3-component architecture with clear separation of concerns:

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

### ProxySettings (Configuration Layer)
- **Purpose**: Pydantic v2 configuration framework with validation
- **Location**: `cryptofeed/proxy.py`
- **Responsibilities**:
  - Environment variable hydration with CRYPTOFEED_PROXY_ prefix
  - Boolean `enabled` flag, optional `default` proxies, per-exchange overrides
  - `get_proxy(exchange_id, connection_type)` resolution: disabled → override → default → none
  - Double-underscore nesting delimiter for complex configurations

### ConnectionProxies and ProxyConfig (Data Layer)
- **Purpose**: Type-safe proxy configuration models
- **Location**: `cryptofeed/proxy.py`
- **Responsibilities**:
  - `ConnectionProxies`: Encapsulates optional HTTP and WebSocket ProxyConfig instances
  - `ProxyConfig`: Validates scheme, hostname, port, timeout during construction
  - Accessor properties (scheme, host, port) for parsed values without repeated parsing
  - Frozen models with extra='forbid' for strict validation

### ProxyInjector (Application Layer)
- **Purpose**: Centralized proxy resolution and connection creation
- **Location**: `cryptofeed/proxy.py`
- **Responsibilities**:
  - `get_http_proxy_url(exchange_id)`: Returns proxy URL for aiohttp session construction
  - `create_websocket_connection()`: Handles SOCKS and HTTP schemes
  - SOCKS4/5: Converts to python-socks parameters for websockets.connect
  - HTTP/HTTPS: Injects Proxy-Connection headers while preserving original parameters
  - Direct fallback when no proxy configured

### Connection Integration (Minimal Modifications)
- **Purpose**: Transparent proxy application to existing connection classes
- **Location**: `cryptofeed/connection.py`
- **Modifications**:
  - Added `exchange_id` parameter to HTTPAsyncConn and WSAsyncConn constructors
  - HTTPAsyncConn: Retrieves proxy URL before aiohttp.ClientSession creation
  - WSAsyncConn: Delegates to ProxyInjector.create_websocket_connection
  - Maintains session reuse and backward compatibility contracts

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
    WSOpen[WSAsyncConn._open] --> ResolveWS[ProxyInjector.get_proxy(exchange,websocket)]
    ResolveWS -->|SOCKS proxy| SockSetup[python-socks parameters]
    SockSetup --> WSConnect[websockets.connect]
    ResolveWS -->|HTTP proxy| HttpHeader[Inject Proxy-Connection header]
    HttpHeader --> WSConnect
    ResolveWS -->|None configured| DirectConnect[websockets.connect]
    WSConnect --> ActiveStream[Active WebSocket Session]
    DirectConnect --> ActiveStream
```

## Requirements Traceability
| Requirement | Design Element |
| --- | --- |
| FR-1 (Activation/Resolution) | Global ProxySettings lifecycle and init_proxy_system |
| FR-2 (HTTP Transport) | HTTPAsyncConn session creation using injector-resolved proxy URLs |
| FR-3 (WebSocket Transport) | ProxyInjector.create_websocket_connection delegation logic |
| FR-4 (Validation/Fallback) | ProxyConfig validation and inheritance semantics |
| FR-5 (Logging/Visibility) | log_proxy_usage() and enhanced error handling |

## Engineering Principles Applied

### START SMALL Principle
- **MVP Implementation**: ~200 lines of core functionality
- **Proven Architecture**: Basic use cases first, extensions based on real needs
- **Clear Upgrade Path**: Extension points documented for future enhancements

### SOLID Principles
- **Single Responsibility**: ProxySettings (config), ProxyInjector (application), Connection classes (transport)
- **Open/Closed**: Extensible through configuration without code changes
- **Liskov Substitution**: Proxy-enabled connections behave identically to direct connections
- **Interface Segregation**: Minimal APIs focused on specific concerns
- **Dependency Inversion**: Abstract ProxySettings interface, not concrete implementations

### YAGNI Principle
- **No Premature Features**: No external proxy managers, health checking, or load balancing
- **Optional Dependencies**: python-socks only required for SOCKS proxy usage
- **Simple Configuration**: Environment variables and YAML, no complex discovery

### KISS Principle
- **3-Component Architecture**: Clear responsibilities and data flow
- **Direct Integration**: Transparent proxy application vs abstract resolver hierarchies
- **Minimal Complexity**: Straightforward validation and error handling

### Zero Breaking Changes
- **Backward Compatibility**: Existing feeds function without modification
- **Optional Functionality**: Proxy routing is opt-in only
- **Legacy Support**: Historical proxy parameters preserved

## Error Handling and Security

### Error Handling Strategy
- **Configuration Validation**: ProxyConfig validation errors surface during loading
- **Dependency Management**: Missing python-socks throws explicit ImportError with guidance
- **Connection Failures**: WebSocket handshake failures propagate through existing error paths
- **Legacy Compatibility**: Historical proxy arguments remain supported when injector returns None

### Security and Observability
- **Credential Protection**: Credentials confined to configuration sources, no URL logging
- **Audit Trails**: Exchange ID, transport type, and proxy scheme logging for observability
- **Operational Visibility**: log_proxy_usage() function provides operational insights
- **No Sensitive Logging**: Full proxy URLs never appear in application logs

## Data and Configuration Model
- **Config Keys**: `enabled`, `default.http`, `default.websocket`, `exchanges.<id>.http`, `exchanges.<id>.websocket`
- **Environment Variable Mapping**: Double underscore (`__`) expands nested structure (e.g., `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL`)
- **Programmatic Use**: Operators can instantiate `ProxySettings` from Python dictionary or YAML payload
- **Timeout Handling**: `ProxyConfig.timeout_seconds` stored for future enhancements but not applied in MVP

## Testing Strategy and Quality Assurance

### Unit Tests (28 tests)
- ProxyConfig parsing for supported and unsupported schemes
- ProxySettings.get_proxy override and fallback ordering
- ProxyInjector SOCKS and HTTP branches with correct websockets.connect parameters
- Configuration validation and error path coverage

### Integration Tests (12 tests)
- HTTPAsyncConn and WSAsyncConn with injector initialized
- Session creation and teardown under proxy settings
- Legacy behavior with injector disabled
- Environment variable configuration loading
- Real-world deployment scenarios

### Configuration Tests
- Environment variable fixtures with double-underscore parsing
- YAML configuration loading and validation
- Precedence testing (environment > YAML > programmatic)

### Dependency Tests
- Missing python-socks simulation for error path validation
- Clear error message and installation guidance verification

## Performance and Scalability

- **Minimal Overhead**: Proxy resolution once per connection open
- **Session Reuse**: aiohttp.ClientSession reuse avoids redundant TCP handshakes
- **Critical Path**: No additional application-layer processing
- **Network Dominance**: Proxy routing latency dominated by network hops

## Files Implemented

### Core Implementation
- `cryptofeed/proxy.py` - Main proxy system implementation (~200 lines)
- `cryptofeed/connection.py` - Connection class integration

### Tests
- `tests/unit/test_proxy_mvp.py` - 28 unit tests
- `tests/integration/test_proxy_integration.py` - 12 integration tests

### Documentation
- `docs/proxy/README.md` - Overview and quick start
- `docs/proxy/user-guide.md` - Configuration and usage patterns  
- `docs/proxy/technical-specification.md` - Implementation details
- `docs/proxy/architecture.md` - Design decisions and principles

## Rejected Alternatives

1. **Plugin-Based System**: Too complex before basic functionality proven
2. **Complex Resolver Hierarchy**: Multiple abstraction layers unnecessary
3. **Decorator Pattern**: More complex than direct integration
4. **External Proxy Managers**: No user demand, violates YAGNI

## Extension Points

The simple architecture provides clear extension points for:
- Health checking (when proxy failures become common)
- External proxy managers (when integration needed)
- Load balancing (when multiple proxies per exchange needed)
- Monitoring (when performance tracking becomes important)

## Risks and Mitigations
- **Optional Dependency Drift**: If python-socks versions change, regression tests assert compatibility
- **Credential Leakage**: Logs never print full proxy URLs; targeted tests validate this
- **Timeout Semantics**: Documentation clarifies current behavior and future roadmap

## Future Enhancements
- Apply `timeout_seconds` to aiohttp and WebSocket clients once validated
- Surface proxy usage metrics via existing metrics subsystem
- Introduce per-exchange circuit breaker or retry policies
- Expand support for authenticated HTTP proxies via header injection

## Success Metrics Achieved

- ✅ **Simple**: ~200 lines of core implementation
- ✅ **Functional**: HTTP and WebSocket proxies work transparently
- ✅ **Type Safe**: Full Pydantic v2 validation with IDE support
- ✅ **Zero Breaking Changes**: All existing code works unchanged
- ✅ **Comprehensive Testing**: 40 tests covering all scenarios
- ✅ **Production Ready**: Environment variables, YAML, Docker/K8s examples
- ✅ **Well Documented**: Comprehensive guides organized by audience
- ✅ **Engineering Principles**: SOLID, KISS, YAGNI, START SMALL applied throughout