# Proxy System Architecture

## Table of Contents

1. [Design Philosophy](#design-philosophy)
2. [Engineering Principles](#engineering-principles)
3. [Architecture Overview](#architecture-overview)
4. [Design Decisions](#design-decisions)
5. [Alternative Approaches](#alternative-approaches)
6. [Extension Points](#extension-points)
7. [Lessons Learned](#lessons-learned)

## Design Philosophy

The cryptofeed proxy system was designed following the **START SMALL** philosophy: solve the core user problem with minimal complexity, then extend based on actual needs rather than theoretical requirements.

### Core Tenets

**"Make the simple case simple, complex cases possible"**
- Basic proxy configuration should require minimal setup
- Advanced scenarios should be achievable without architectural changes
- Zero breaking changes to existing user code

**"Functional Requirements over Non-Functional Requirements"**
- Focus on core functionality first (HTTP/WebSocket proxy support)
- Defer enterprise features (HA, monitoring, load balancing) until proven necessary
- Prioritize working software over perfect software

**"Type Safety without Complexity"**
- Use Pydantic v2 for configuration validation
- Provide clear error messages for misconfigurations
- Enable IDE support and autocomplete

## Engineering Principles

The proxy system strictly adheres to established engineering principles:

### SOLID Principles

**Single Responsibility Principle (SRP)**
- `ProxyConfig`: Only validates and stores single proxy configuration
- `ProxySettings`: Only manages configuration loading and resolution
- `ProxyInjector`: Only applies proxy to connections
- `HTTPAsyncConn`/`WSAsyncConn`: Only handle connections (proxy integration is minimal addition)

**Open/Closed Principle (OCP)**
- Existing connection classes extended with proxy support, not modified
- New proxy types can be added without changing existing code
- Configuration system is extensible via Pydantic models

**Liskov Substitution Principle (LSP)**
- Proxy-enabled connections work identically to direct connections
- All proxy types conform to same interface contracts
- Fallback behavior preserves original functionality

**Interface Segregation Principle (ISP)**
- Minimal proxy interfaces - no fat interfaces
- Separate HTTP and WebSocket proxy configuration
- Optional proxy injection - no forced dependencies

**Dependency Inversion Principle (DIP)**
- Depend on `ProxySettings` abstraction, not concrete implementations
- Connection classes depend on proxy injection interface, not specific proxy types
- Configuration loading abstracted through Pydantic Settings

### Additional Principles

**KISS (Keep It Simple, Stupid)**
- Simple 3-component architecture instead of complex plugin systems
- Direct proxy application instead of abstract resolver hierarchies
- Clear data flow: Settings → Injector → Connections

**YAGNI (You Aren't Gonna Need It)**
- No external proxy managers until proven necessary
- No health checking until proxy failures become common
- No load balancing until performance becomes an issue
- No complex caching until proven to be a bottleneck

**DRY (Don't Repeat Yourself)**
- Single proxy configuration model for all proxy types
- Shared resolution logic for all exchanges
- Common error handling patterns

**START SMALL**
- MVP implementation first (~150 lines of code)
- Prove the architecture works with basic use cases
- Extend based on actual user feedback, not theoretical needs

## Architecture Overview

### Component Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ ProxySettings   │    │ ProxyInjector    │    │ Connection      │
│ (Pydantic v2)   │───▶│ (Stateless)      │───▶│ Classes         │
│                 │    │                  │    │                 │
│ - Validation    │    │ - HTTP Proxy     │    │ - HTTPAsyncConn │
│ - Type Safety   │    │ - WebSocket      │    │ - WSAsyncConn   │
│ - Settings      │    │ - Transparent    │    │ - Minimal Mods  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Data Flow

```
1. Configuration Loading:
   Environment Variables → ProxySettings → Validation → Storage

2. Proxy Resolution:
   Exchange ID + Connection Type → ProxySettings.get_proxy() → ProxyConfig

3. Proxy Application:
   ProxyConfig → ProxyInjector → aiohttp.ClientSession(proxy=url)
                                → websockets.connect(proxy_*=...)

4. Connection Creation:
   HTTPAsyncConn(exchange_id="binance") → get_proxy_injector() → proxy applied
```

### Component Responsibilities

| Component | Responsibility | Input | Output |
|-----------|----------------|-------|--------|
| `ProxyConfig` | Validate single proxy configuration | URL, timeout | Validated config |
| `ConnectionProxies` | Group HTTP/WebSocket proxy configs | HTTP/WS configs | Grouped config |
| `ProxySettings` | Load and resolve proxy configuration | Env vars, files | Proxy resolution |
| `ProxyInjector` | Apply proxy to connections | Exchange ID | Proxy application |
| `HTTPAsyncConn` | HTTP connections with proxy support | Proxy URL | HTTP session |
| `WSAsyncConn` | WebSocket connections with proxy support | Proxy config | WS connection |

## Design Decisions

### Decision 1: Pydantic v2 for Configuration

**Choice:** Use Pydantic v2 with pydantic-settings for configuration management

**Alternatives Considered:**
- Raw dictionaries with manual validation
- dataclasses with custom validation
- Configuration files only (YAML/JSON)
- Environment variables only

**Rationale:**
- ✅ Type safety with runtime validation
- ✅ Automatic environment variable loading
- ✅ Clear error messages for misconfigurations
- ✅ IDE support and autocomplete
- ✅ Extensible for future configuration needs

**Trade-offs:**
- ➕ Excellent developer experience
- ➕ Robust validation and error handling
- ➖ Additional dependency (but already used in cryptofeed)
- ➖ Learning curve for Pydantic v2 syntax

### Decision 2: Global Singleton Pattern

**Choice:** Use global singleton for proxy injector with explicit initialization

**Alternatives Considered:**
- Dependency injection throughout application
- Context managers for proxy scope
- Per-connection proxy configuration
- Service locator pattern

**Rationale:**
- ✅ Zero code changes for existing applications
- ✅ Simple initialization model
- ✅ Clear system-wide proxy state
- ✅ Easy to disable/enable globally

**Trade-offs:**
- ➕ Transparent to existing code
- ➕ Simple to understand and use
- ➖ Global state (testing considerations)
- ➖ Less flexible than dependency injection

**Implementation:**
```python
# Global state (simplified singleton)
_proxy_injector: Optional[ProxyInjector] = None

def init_proxy_system(settings: ProxySettings) -> None:
    """Initialize proxy system with settings."""
    global _proxy_injector
    if settings.enabled:
        _proxy_injector = ProxyInjector(settings)
    else:
        _proxy_injector = None
```

### Decision 3: Minimal Connection Class Modifications

**Choice:** Minimal changes to existing `HTTPAsyncConn` and `WSAsyncConn` classes

**Alternatives Considered:**
- Complete rewrite of connection classes
- Proxy-specific connection class hierarchy
- Decorator pattern for proxy functionality
- Mixin classes for proxy support

**Rationale:**
- ✅ Preserve existing functionality
- ✅ Minimal risk of breaking changes
- ✅ Easy to review and understand changes
- ✅ Backward compatibility maintained

**Changes Made:**
```python
# HTTPAsyncConn - added exchange_id parameter and proxy resolution
def __init__(self, conn_id: str, proxy: StrOrURL = None, exchange_id: str = None):
    self.exchange_id = exchange_id  # New parameter

async def _open(self):
    # Get proxy URL from proxy system
    proxy_url = None
    injector = get_proxy_injector()
    if injector and self.exchange_id:
        proxy_url = injector.get_http_proxy_url(self.exchange_id)
    
    # Use proxy or fallback to legacy parameter
    proxy = proxy_url or self.proxy
    self.conn = aiohttp.ClientSession(proxy=proxy)
```

### Decision 4: HTTP vs WebSocket Proxy Implementation

**Choice:** Different implementation approaches for HTTP vs WebSocket proxies

**HTTP Proxy Approach:**
- Use aiohttp's built-in proxy support
- Set proxy at `ClientSession` creation time
- Leverage existing HTTP proxy standards

**WebSocket Proxy Approach:**
- Use python-socks library for SOCKS proxies
- Limited HTTP proxy support (not all servers support it)
- Transparent integration with websockets library

**Rationale:**
- ✅ Leverage existing, well-tested libraries
- ✅ Follow established patterns for each protocol
- ✅ Minimal custom proxy implementation
- ✅ Clear separation of concerns

**Trade-offs:**
- ➕ Robust, battle-tested proxy implementations
- ➕ Standards-compliant proxy support
- ➖ Different APIs for HTTP vs WebSocket
- ➖ Additional dependency for SOCKS WebSocket support

### Decision 5: Exchange-Specific Configuration

**Choice:** Support per-exchange proxy overrides with default fallback

**Configuration Model:**
```python
class ProxySettings(BaseSettings):
    default: Optional[ConnectionProxies] = None        # Default for all exchanges
    exchanges: Dict[str, ConnectionProxies] = {}       # Exchange-specific overrides
    
    def get_proxy(self, exchange_id: str, connection_type: str) -> Optional[ProxyConfig]:
        # 1. Check exchange-specific override
        # 2. Fall back to default
        # 3. Return None if not configured
```

**Rationale:**
- ✅ Supports simple use case (one proxy for all)
- ✅ Supports complex use case (different proxies per exchange)
- ✅ Regional compliance requirements
- ✅ Performance optimization opportunities

**Alternative Considered:**
```python
# Rejected: Complex rule-based system
class ProxyRules:
    def apply_rules(self, exchange: str, region: str, time: datetime) -> ProxyConfig:
        # Complex rule evaluation logic
```

**Why Rejected:** YAGNI - no user has requested rule-based proxy selection

## Alternative Approaches

### Rejected Architecture 1: Plugin-Based System

**Approach:**
```python
class ProxyManagerPlugin(Protocol):
    async def resolve_proxy(self, exchange_id: str, connection_type: str) -> Optional[ProxyConfig]:
        ...
    async def health_check(self, proxy: ProxyConfig) -> bool:
        ...

class ProxyResolver:
    def __init__(self, plugins: List[ProxyManagerPlugin]):
        self.plugins = plugins
```

**Why Rejected:**
- ❌ Over-engineering before basic functionality is proven
- ❌ Complex plugin loading and management
- ❌ No user has requested external proxy managers
- ❌ Violates START SMALL principle

### Rejected Architecture 2: Complex Resolver Hierarchy

**Approach:**
```python
class ProxyResolver(ABC):
    @abstractmethod
    async def resolve(self, context: ProxyContext) -> Optional[ProxyConfig]:
        ...

class RegionalProxyResolver(ProxyResolver):
    async def resolve(self, context: ProxyContext) -> Optional[ProxyConfig]:
        region = await self.detect_region(context.exchange_id)
        return self.regional_proxies.get(region)

class LoadBalancingProxyResolver(ProxyResolver):
    async def resolve(self, context: ProxyContext) -> Optional[ProxyConfig]:
        proxies = await self.get_healthy_proxies(context.exchange_id)
        return self.select_least_loaded(proxies)
```

**Why Rejected:**
- ❌ Complex before simple is working
- ❌ Multiple abstraction layers
- ❌ Difficult to test and debug
- ❌ No evidence these features are needed

### Rejected Architecture 3: Decorator Pattern

**Approach:**
```python
class ProxyConnection:
    def __init__(self, wrapped_connection: Connection, proxy_config: ProxyConfig):
        self.wrapped = wrapped_connection
        self.proxy = proxy_config
    
    async def connect(self):
        # Apply proxy logic then delegate to wrapped connection
        return await self.wrapped.connect()
```

**Why Rejected:**
- ❌ More complex than direct integration
- ❌ Additional abstraction layer
- ❌ Harder to understand data flow
- ❌ No significant benefits over direct approach

## Extension Points

The simple architecture provides clear extension points for future needs:

### Adding Health Checking

**When Needed:** If proxy failures become common and automatic failover is required

**Extension Approach:**
```python
class ProxyInjector:
    def __init__(self, settings: ProxySettings, health_checker: Optional[HealthChecker] = None):
        self.settings = settings
        self.health_checker = health_checker  # Extension point
    
    def get_http_proxy_url(self, exchange_id: str) -> Optional[str]:
        proxy = self.settings.get_proxy(exchange_id, "http")
        if proxy and (not self.health_checker or self.health_checker.is_healthy(proxy)):
            return proxy.url
        return None
```

### Adding External Proxy Managers

**When Needed:** If integration with external proxy management systems is required

**Extension Approach:**
```python
class ProxySettings:
    external_manager: Optional[str] = None  # Plugin module name
    
    async def get_proxy(self, exchange_id: str, connection_type: str) -> Optional[ProxyConfig]:
        # Try external manager first (if configured)
        if self.external_manager:
            proxy = await self._call_external_manager(exchange_id, connection_type)
            if proxy:
                return proxy
        
        # Fall back to static configuration
        return self._get_static_proxy(exchange_id, connection_type)
```

### Adding Load Balancing

**When Needed:** If multiple proxies per exchange are needed for performance

**Extension Approach:**
```python
class ConnectionProxies(BaseModel):
    http: Union[ProxyConfig, List[ProxyConfig]] = None  # Support lists
    websocket: Union[ProxyConfig, List[ProxyConfig]] = None

class ProxyInjector:
    def get_http_proxy_url(self, exchange_id: str) -> Optional[str]:
        proxy_config = self.settings.get_proxy(exchange_id, 'http')
        if isinstance(proxy_config, list):
            return self.load_balancer.select(proxy_config).url
        return proxy_config.url if proxy_config else None
```

### Adding Monitoring

**When Needed:** If proxy performance monitoring becomes important

**Extension Approach:**
```python
class ProxyInjector:
    def __init__(self, settings: ProxySettings, monitor: Optional[ProxyMonitor] = None):
        self.settings = settings
        self.monitor = monitor  # Extension point
    
    def get_http_proxy_url(self, exchange_id: str) -> Optional[str]:
        proxy_url = # ... resolve proxy
        if self.monitor and proxy_url:
            self.monitor.track_proxy_usage(exchange_id, 'http', proxy_url)
        return proxy_url
```

## Lessons Learned

### What Worked Well

**1. START SMALL Approach**
- Implementing MVP first proved the architecture works
- Simple 3-component design is easy to understand and maintain
- Focus on core functionality prevented over-engineering

**2. Pydantic v2 Configuration**
- Type safety caught configuration errors early
- Environment variable loading simplified deployment
- Clear validation errors improved debugging experience

**3. Minimal Integration**
- Adding `exchange_id` parameter was non-breaking change
- Existing code continues to work unchanged
- Simple fallback mechanism preserved backward compatibility

**4. Transparent Application**
- Zero code changes for end users
- Proxy configuration separate from business logic
- Easy to enable/disable for testing

### What Could Be Improved

**1. WebSocket Proxy Complexity**
- HTTP proxy support for WebSocket is limited
- Dependency on python-socks adds complexity
- Different APIs for HTTP vs WebSocket proxies

**2. Global State Testing**
- Singleton pattern makes testing slightly more complex
- Need to reset proxy system between tests
- Parallel test execution considerations

**3. Documentation Organization**
- Initially scattered across multiple spec files
- Needed consolidation for better discoverability
- User vs developer documentation separation

### Key Insights

**1. YAGNI is Powerful**
- Deferring complex features until proven necessary saved significant development time
- Simple architecture is easier to extend than complex one is to simplify
- User feedback is more valuable than theoretical requirements

**2. Type Safety Pays Off**
- Pydantic validation caught many configuration errors during development
- Clear error messages reduced support burden
- IDE support improved developer experience

**3. Backward Compatibility Enables Adoption**
- Zero breaking changes removed adoption friction
- Existing applications could benefit immediately
- Gradual migration path for advanced features

**4. Start Small, Think Big**
- Simple architecture has clear extension points
- MVP proves concepts before investing in complexity
- User feedback guides feature priorities

### Anti-Patterns Avoided

**1. Golden Hammer**
- Didn't force single solution for all proxy types
- Used appropriate libraries for each use case
- Avoided custom proxy implementation

**2. Premature Optimization**
- No caching until performance proven to be issue
- No load balancing until multiple proxies needed
- No health checking until failures become common

**3. Feature Creep**
- Resisted adding "nice to have" features
- Focused on solving actual user problems
- Maintained clear scope boundaries

**4. Over-Abstraction**
- Avoided complex plugin architectures
- Kept interfaces minimal and focused
- Preferred composition over inheritance

## Conclusion

The cryptofeed proxy system demonstrates that following engineering principles and starting small can produce robust, extensible architecture. The key lessons are:

1. **Solve real problems, not theoretical ones** - Focus on actual user needs
2. **Simple architecture is easier to extend** - Avoid premature complexity
3. **Type safety and validation pay off** - Catch errors early with good tooling
4. **Backward compatibility enables adoption** - Remove friction for existing users
5. **Document design decisions** - Help future maintainers understand choices

The architecture successfully balances simplicity with extensibility, providing a solid foundation for future proxy-related features while solving current user problems with minimal complexity.

This architecture serves as an example of how to apply engineering principles to create maintainable, extensible systems that start small and grow based on actual needs rather than theoretical requirements.