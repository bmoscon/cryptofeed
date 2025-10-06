# Proxy System Technical Specification

## Table of Contents

1. [API Reference](#api-reference)
2. [Implementation Details](#implementation-details)
3. [Integration Points](#integration-points)
4. [Testing](#testing)
5. [Error Handling](#error-handling)
6. [Dependencies](#dependencies)

## API Reference

### Core Classes

#### ProxyConfig

**Purpose:** Single proxy configuration with URL validation and timeout settings.

```python
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Literal
from urllib.parse import urlparse

class ProxyConfig(BaseModel):
    """Single proxy configuration with URL validation."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    
    url: str = Field(..., description="Proxy URL (e.g., socks5://user:pass@host:1080)")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    
    @field_validator('url')
    @classmethod
    def validate_proxy_url(cls, v: str) -> str:
        """Validate proxy URL format and scheme."""
        parsed = urlparse(v)
        
        # Check for valid URL format - should have '://' for scheme
        if '://' not in v:
            raise ValueError("Proxy URL must include scheme (http, socks5, socks4)")
            
        if not parsed.scheme:
            raise ValueError("Proxy URL must include scheme (http, socks5, socks4)")
        if parsed.scheme not in ('http', 'https', 'socks4', 'socks5'):
            raise ValueError(f"Unsupported proxy scheme: {parsed.scheme}")
        if not parsed.hostname:
            raise ValueError("Proxy URL must include hostname")
        if not parsed.port:
            raise ValueError("Proxy URL must include port")
        return v
    
    @property
    def scheme(self) -> str:
        """Extract proxy scheme."""
        return urlparse(self.url).scheme
    
    @property
    def host(self) -> str:
        """Extract proxy hostname."""
        return urlparse(self.url).hostname
    
    @property
    def port(self) -> int:
        """Extract proxy port."""
        return urlparse(self.url).port
```

**Supported URL Formats:**
- `http://proxy.example.com:8080`
- `https://proxy.example.com:8443`
- `socks4://proxy.example.com:1080`
- `socks5://user:pass@proxy.example.com:1080`

#### ConnectionProxies

**Purpose:** Proxy configuration for different connection types (HTTP vs WebSocket).

```python
class ConnectionProxies(BaseModel):
    """Proxy configuration for different connection types."""
    model_config = ConfigDict(extra='forbid')
    
    http: Optional[ProxyConfig] = Field(default=None, description="HTTP/REST proxy")
    websocket: Optional[ProxyConfig] = Field(default=None, description="WebSocket proxy")
```

#### ProxySettings

**Purpose:** Main configuration class with environment variable support and proxy resolution logic.

```python
from pydantic_settings import BaseSettings

class ProxySettings(BaseSettings):
    """Proxy configuration using pydantic-settings."""
    model_config = ConfigDict(
        env_prefix='CRYPTOFEED_PROXY_',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='forbid'
    )
    
    enabled: bool = Field(default=False, description="Enable proxy functionality")
    
    # Default proxy for all exchanges
    default: Optional[ConnectionProxies] = Field(
        default=None, 
        description="Default proxy configuration for all exchanges"
    )
    
    # Exchange-specific overrides
    exchanges: Dict[str, ConnectionProxies] = Field(
        default_factory=dict,
        description="Exchange-specific proxy overrides"
    )
    
    def get_proxy(self, exchange_id: str, connection_type: Literal['http', 'websocket']) -> Optional[ProxyConfig]:
        """Get proxy configuration for specific exchange and connection type."""
        if not self.enabled:
            return None
        
        # Check exchange-specific override first
        if exchange_id in self.exchanges:
            proxy = getattr(self.exchanges[exchange_id], connection_type, None)
            if proxy is not None:
                return proxy
        
        # Fall back to default
        if self.default:
            return getattr(self.default, connection_type, None)
        
        return None
```

**Environment Variable Mapping:**
- `CRYPTOFEED_PROXY_ENABLED` → `enabled`
- `CRYPTOFEED_PROXY_DEFAULT__HTTP__URL` → `default.http.url`
- `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL` → `exchanges.binance.http.url`

#### ProxyInjector

**Purpose:** Core proxy injection logic for HTTP and WebSocket connections.

```python
class ProxyInjector:
    """Simple proxy injection for HTTP and WebSocket connections."""
    
    def __init__(self, proxy_settings: ProxySettings):
        self.settings = proxy_settings
    
    def get_http_proxy_url(self, exchange_id: str) -> Optional[str]:
        """Get HTTP proxy URL for exchange if configured."""
        proxy_config = self.settings.get_proxy(exchange_id, 'http')
        return proxy_config.url if proxy_config else None
    
    def apply_http_proxy(self, session: aiohttp.ClientSession, exchange_id: str) -> None:
        """Apply HTTP proxy to aiohttp session if configured."""
        # Note: aiohttp proxy is set at ClientSession creation time, not after
        # This method is kept for interface compatibility
        # Use get_http_proxy_url() during session creation instead
        pass
    
    async def create_websocket_connection(self, url: str, exchange_id: str, **kwargs):
        """Create WebSocket connection with proxy if configured."""
        proxy_config = self.settings.get_proxy(exchange_id, 'websocket')

        if not proxy_config:
            return await websockets.connect(url, **kwargs)

        connect_kwargs = dict(kwargs)
        scheme = proxy_config.scheme

        if scheme in ('socks4', 'socks5'):
            try:
                __import__('python_socks')
            except ModuleNotFoundError as exc:
                raise ImportError(
                    "python-socks library required for SOCKS proxy support. Install with: pip install python-socks"
                ) from exc
        elif scheme in ('http', 'https'):
            header_key = 'extra_headers' if 'extra_headers' in connect_kwargs else 'additional_headers'
            existing_headers = connect_kwargs.get(header_key, {})
            headers = dict(existing_headers) if existing_headers else {}
            headers.setdefault('Proxy-Connection', 'keep-alive')
            connect_kwargs[header_key] = headers

        connect_kwargs['proxy'] = proxy_config.url
        return await websockets.connect(url, **connect_kwargs)
```

### Global Functions

#### init_proxy_system(settings: ProxySettings) → None

Initialize the global proxy system with given settings.

```python
def init_proxy_system(settings: ProxySettings) -> None:
    """Initialize proxy system with settings."""
    global _proxy_injector
    if settings.enabled:
        _proxy_injector = ProxyInjector(settings)
    else:
        _proxy_injector = None
```

#### get_proxy_injector() → Optional[ProxyInjector]

Get the current global proxy injector instance.

```python
def get_proxy_injector() -> Optional[ProxyInjector]:
    """Get global proxy injector instance."""
    return _proxy_injector
```

#### load_proxy_settings() → ProxySettings

Load proxy settings from environment variables and configuration files.

```python
def load_proxy_settings() -> ProxySettings:
    """Load proxy settings from environment or configuration."""
    return ProxySettings()
```

## Implementation Details

### HTTP Proxy Integration

HTTP proxy support is implemented through aiohttp's built-in proxy support:

```python
# In HTTPAsyncConn._open()
async def _open(self):
    # Get proxy URL if configured through proxy system
    proxy_url = None
    injector = get_proxy_injector()
    if injector and self.exchange_id:
        proxy_url = injector.get_http_proxy_url(self.exchange_id)
    
    # Use proxy URL if available, otherwise fall back to legacy proxy parameter
    proxy = proxy_url or self.proxy
    
    self.conn = aiohttp.ClientSession(proxy=proxy)
```

**Key Points:**
- Proxy must be set at `ClientSession` creation time
- Legacy `proxy` parameter is preserved for backward compatibility
- Proxy URL is resolved per connection based on `exchange_id`

### WebSocket Proxy Integration

WebSocket proxy support uses the `python-socks` library for SOCKS proxies:

```python
# In WSAsyncConn._open()
async def _open(self):
    # Use proxy injector if available
    injector = get_proxy_injector()
    if injector and self.exchange_id:
        self.conn = await injector.create_websocket_connection(self.address, self.exchange_id, **self.ws_kwargs)
    else:
        self.conn = await connect(self.address, **self.ws_kwargs)
```

**Proxy Type Support:**
- **SOCKS4/SOCKS5**: Full support via `python-socks`
- **HTTP/HTTPS**: Limited support via headers (not all servers support this)

### Configuration Loading

Configuration is loaded using Pydantic Settings with the following precedence:

1. **Explicit Python values** (highest precedence)
2. **Environment variables**
3. **Configuration files** (if implemented)
4. **Default values** (lowest precedence)

**Environment Variable Naming:**
- Prefix: `CRYPTOFEED_PROXY_`
- Nested delimiter: `__` (double underscore)
- Case insensitive

Example: `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__TIMEOUT_SECONDS=15`

## Integration Points

### FeedHandler Initialization
- `FeedHandler` calls `init_proxy_system` during construction.
- Configuration precedence is **environment variables → YAML config (`proxy` block) → explicit `proxy_settings` argument**.
- Passing a `ProxySettings` instance to `FeedHandler(proxy_settings=...)` provides a fallback when no external configuration is supplied.

### Connection Classes

The proxy system integrates with existing connection classes with minimal modifications:

#### HTTPAsyncConn

**Modified Constructor:**
```python
def __init__(self, conn_id: str, proxy: StrOrURL = None, exchange_id: str = None):
    """
    conn_id: str
        id associated with the connection
    proxy: str, URL
        proxy url (GET only) - deprecated, use proxy system instead
    exchange_id: str
        exchange identifier for proxy configuration
    """
    super().__init__(f'{conn_id}.http.{self.conn_count}')
    self.proxy = proxy  # Legacy parameter
    self.exchange_id = exchange_id  # New parameter for proxy system
```

**Modified _open() Method:**
- Resolves proxy URL through proxy system if `exchange_id` is provided
- Falls back to legacy `proxy` parameter for backward compatibility
- Creates `ClientSession` with resolved proxy URL

#### WSAsyncConn

**Modified Constructor:**
```python
def __init__(self, address: str, conn_id: str, authentication=None, subscription=None, exchange_id: str = None, **kwargs):
    """
    exchange_id: str
        exchange identifier for proxy configuration
    """
    self.exchange_id = exchange_id  # New parameter
    # ... existing initialization
```

**Modified _open() Method:**
- Uses `ProxyInjector.create_websocket_connection()` if proxy system is active
- Falls back to direct `websockets.connect()` for backward compatibility

### Feed Classes

Feed classes pass `exchange_id` to connection constructors:

```python
class CcxtFeed(Feed):
    def __init__(self, exchange_id: str, **kwargs):
        self.exchange_id = exchange_id
        super().__init__(**kwargs)
    
    def _create_http_connection(self, conn_id: str, **kwargs):
        """Create HTTP connection with exchange_id for proxy configuration."""
        return HTTPAsyncConn(conn_id, exchange_id=self.exchange_id, **kwargs)
    
    def _create_websocket_connection(self, address: str, conn_id: str, **kwargs):
        """Create WebSocket connection with exchange_id for proxy configuration."""
        return WSAsyncConn(address, conn_id, exchange_id=self.exchange_id, **kwargs)
```

## Testing

### Unit Tests

The proxy system includes comprehensive unit tests:

**Configuration Testing:**
```python
def test_proxy_config_validation():
    """Test ProxyConfig validation."""
    # Valid configurations
    config = ProxyConfig(url="socks5://user:pass@proxy:1080")
    assert config.scheme == "socks5"
    assert config.host == "proxy"
    assert config.port == 1080
    
    # Invalid configurations
    with pytest.raises(ValueError, match="Proxy URL must include scheme"):
        ProxyConfig(url="proxy.example.com:1080")

def test_proxy_settings_resolution():
    """Test proxy resolution logic."""
    settings = ProxySettings(
        enabled=True,
        default=ConnectionProxies(http=ProxyConfig(url="socks5://default:1080")),
        exchanges={"binance": ConnectionProxies(http=ProxyConfig(url="http://binance:8080"))}
    )
    
    # Exchange-specific override
    assert settings.get_proxy("binance", "http").url == "http://binance:8080"
    
    # Default fallback
    assert settings.get_proxy("coinbase", "http").url == "socks5://default:1080"
    
    # Disabled proxy
    settings.enabled = False
    assert settings.get_proxy("binance", "http") is None
```

**Injection Testing:**
```python
def test_proxy_injector():
    """Test ProxyInjector functionality."""
    settings = ProxySettings(
        enabled=True,
        default=ConnectionProxies(http=ProxyConfig(url="socks5://default:1080")),
        exchanges={"binance": ConnectionProxies(http=ProxyConfig(url="http://binance:8080"))}
    )
    
    injector = ProxyInjector(settings)
    
    # Test proxy URL retrieval
    assert injector.get_http_proxy_url("binance") == "http://binance:8080"
    assert injector.get_http_proxy_url("coinbase") == "socks5://default:1080"
```

### Integration Tests

**Connection Testing:**
```python
@pytest.mark.asyncio
async def test_http_connection_with_proxy():
    """Test HTTP connection applies proxy injection."""
    settings = ProxySettings(
        enabled=True,
        default=ConnectionProxies(http=ProxyConfig(url="socks5://test:1080"))
    )
    init_proxy_system(settings)
    
    try:
        conn = HTTPAsyncConn("test", exchange_id="binance")
        await conn._open()
        
        # Verify connection was created successfully
        assert conn.is_open
        assert conn.conn is not None
        
    finally:
        if conn.is_open:
            await conn.close()
        init_proxy_system(ProxySettings(enabled=False))
```

**Environment Variable Testing:**
```python
def test_environment_variable_loading():
    """Test loading configuration from environment variables."""
    os.environ["CRYPTOFEED_PROXY_ENABLED"] = "true"
    os.environ["CRYPTOFEED_PROXY_DEFAULT__HTTP__URL"] = "socks5://test:1080"
    
    try:
        settings = load_proxy_settings()
        assert settings.enabled
        assert settings.default.http.url == "socks5://test:1080"
    finally:
        os.environ.pop("CRYPTOFEED_PROXY_ENABLED", None)
        os.environ.pop("CRYPTOFEED_PROXY_DEFAULT__HTTP__URL", None)
```

### CI Testing Checklist

| Step | Command | Purpose |
| --- | --- | --- |
| 1 | `pytest tests/unit/test_proxy_mvp.py` | Validate configuration precedence, injector logic, and HTTP/WS proxy branches |
| 2 | `pytest tests/integration/test_proxy_integration.py` | Exercise real connection classes with proxy injection and cleanup |
| 3 | `pytest tests/unit/test_proxy_mvp.py::TestFeedHandlerProxyInitialization::test_http_async_conn_reuses_session_with_proxy` | Guard against regressions in proxy-enabled session reuse |
| 4 | Matrix job without `python-socks` installed | Ensure ImportError messaging for SOCKS proxies remains accurate |

### Test Execution

```bash
# Run all proxy tests
python -m pytest tests/unit/test_proxy_mvp.py -v
python -m pytest tests/integration/test_proxy_integration.py -v

# Run specific test categories
python -m pytest -k "proxy" -v
python -m pytest -k "ProxyConfig" -v
```

## Error Handling

### Configuration Errors

**Invalid Proxy URLs:**
```python
# Raises ValueError with descriptive message
try:
    ProxyConfig(url="invalid-url")
except ValueError as e:
    print(e)  # "Proxy URL must include scheme (http, socks5, socks4)"
```

**Unsupported Proxy Schemes:**
```python
try:
    ProxyConfig(url="ftp://proxy:21")
except ValueError as e:
    print(e)  # "Unsupported proxy scheme: ftp"
```

**Invalid Timeouts:**
```python
try:
    ProxyConfig(url="socks5://proxy:1080", timeout_seconds=0)
except ValueError as e:
    print(e)  # Validation error for timeout range
```

### Runtime Errors

**Missing Dependencies:**
```python
# When python-socks is not installed but SOCKS WebSocket proxy is configured
try:
    await injector.create_websocket_connection("wss://example.com", "binance")
except ImportError as e:
    print(e)  # "python-socks library required for SOCKS proxy support. Install with: pip install python-socks"
```

**Proxy Connection Failures:**
- HTTP proxy failures are handled by aiohttp and raise appropriate connection errors
- WebSocket proxy failures are handled by websockets/python-socks libraries
- Both preserve original error messages for debugging

### Graceful Degradation

**Disabled Proxy System:**
```python
# When proxy system is disabled, connections work normally
settings = ProxySettings(enabled=False)
init_proxy_system(settings)

# All connections use direct routes
conn = HTTPAsyncConn("test", exchange_id="binance")  # Works without proxy
```

**Missing Exchange Configuration:**
```python
# When exchange is not configured, uses default proxy
settings = ProxySettings(
    enabled=True,
    default=ConnectionProxies(http=ProxyConfig(url="socks5://default:1080"))
    # No exchange-specific config
)

# Uses default proxy for all exchanges
proxy_url = injector.get_http_proxy_url("unknown_exchange")  # Returns default proxy URL
```

## Dependencies

### Required Dependencies

**Core Dependencies:**
- `pydantic >= 2.0` - Configuration validation and type safety
- `pydantic-settings` - Environment variable loading
- `aiohttp` - HTTP connections and proxy support
- `websockets` - WebSocket connections

**Standard Library:**
- `urllib.parse` - URL parsing and validation
- `typing` - Type hints and annotations

### Optional Dependencies

**SOCKS Proxy Support:**
- `python-socks` - SOCKS4/SOCKS5 proxy support for WebSocket connections

**Installation:**
```bash
# Core proxy support (included with cryptofeed)
pip install pydantic pydantic-settings aiohttp websockets

# SOCKS WebSocket support (optional)
pip install python-socks
```

### Dependency Matrix

| Feature | Required Dependencies | Optional Dependencies |
|---------|----------------------|----------------------|
| HTTP Proxy | `pydantic`, `pydantic-settings`, `aiohttp` | None |
| SOCKS HTTP Proxy | `pydantic`, `pydantic-settings`, `aiohttp` | None |
| HTTP WebSocket Proxy | `pydantic`, `pydantic-settings`, `websockets` | None |
| SOCKS WebSocket Proxy | `pydantic`, `pydantic-settings`, `websockets` | `python-socks` |

### Version Compatibility

**Pydantic v2 Requirement:**
- The proxy system requires Pydantic v2 for proper field validation syntax
- Uses `@field_validator` decorator (v2 syntax) instead of `@validator` (v1 syntax)
- Uses `ConfigDict` instead of `Config` class

**Python Version:**
- Requires Python 3.8+ (due to Pydantic v2 requirement)
- Tested with Python 3.8, 3.9, 3.10, 3.11, 3.12

**Library Versions:**
```
pydantic >= 2.0.0
pydantic-settings >= 2.0.0
aiohttp >= 3.8.0
websockets >= 10.0
python-socks >= 2.0.0  # Optional
```

This technical specification provides complete implementation details for developers who need to understand, extend, or debug the proxy system. For usage examples, see the [User Guide](user-guide.md). For design rationale, see the [Architecture](architecture.md) document.
