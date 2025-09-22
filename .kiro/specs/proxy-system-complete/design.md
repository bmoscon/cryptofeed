# Design Document

## Architecture Overview

Simple 3-component architecture following START SMALL principles:

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

## Core Components

### 1. ProxySettings (Pydantic v2)
**Purpose**: Configuration validation and proxy resolution
**Location**: `cryptofeed/proxy.py`
**Key Features**:
- Environment variable loading with `CRYPTOFEED_PROXY_*` prefix
- Exchange-specific overrides with default fallback
- Full Pydantic v2 validation with clear error messages

### 2. ProxyInjector (Stateless)  
**Purpose**: Apply proxy configuration to connections
**Location**: `cryptofeed/proxy.py`
**Key Features**:
- HTTP proxy URL resolution for aiohttp sessions
- WebSocket proxy support via python-socks library
- Transparent application based on exchange_id

### 3. Connection Integration (Minimal Changes)
**Purpose**: Integrate proxy support into existing connection classes
**Location**: `cryptofeed/connection.py`
**Key Features**:
- Added `exchange_id` parameter to HTTPAsyncConn and WSAsyncConn
- Proxy resolution during connection creation
- Backward compatibility with legacy proxy parameter

## Design Decisions

### Decision 1: Pydantic v2 for Configuration
**Rationale**: Type safety, validation, environment variable support, IDE integration

### Decision 2: Global Singleton Pattern
**Rationale**: Zero code changes for existing applications, simple initialization

### Decision 3: Minimal Connection Modifications
**Rationale**: Preserve existing functionality, minimal risk, backward compatibility

### Decision 4: Different HTTP vs WebSocket Implementation
**Rationale**: Leverage existing libraries (aiohttp proxy, python-socks)

## Engineering Principles Applied

- **START SMALL**: MVP functionality only (~150 lines)
- **YAGNI**: No external managers, HA, monitoring until proven needed
- **KISS**: Simple 3-component architecture vs complex plugin systems
- **SOLID**: Clear separation of responsibilities
- **Zero Breaking Changes**: Existing code works unchanged

## Files Implemented

### Core Implementation
- `cryptofeed/proxy.py` - Main proxy system implementation
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

## Success Metrics Achieved

- ✅ **Simple**: <200 lines of code (achieved ~150 lines)
- ✅ **Functional**: HTTP and WebSocket proxies work transparently
- ✅ **Type Safe**: Full Pydantic v2 validation
- ✅ **Zero Breaking Changes**: Existing code unchanged
- ✅ **Testable**: 40 comprehensive tests
- ✅ **Production Ready**: Environment variables, YAML, error handling