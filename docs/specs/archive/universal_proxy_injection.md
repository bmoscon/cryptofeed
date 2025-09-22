# Universal Transparent Proxy Injection

## Executive Summary

**Objective**: Implement transparent proxy injection for ALL cryptofeed connections with **zero code changes** required for existing exchanges and user code.

**Core Principle**: Proxy handling is infrastructure-level, completely transparent to application logic. Existing exchanges work identically with or without proxies configured.

## Architecture Overview

### Transparent Injection Flow

```
User Code (Unchanged) → Connection Factory → Transparent Proxy Injection → Transport Layer
     ↓                      ↓                        ↓                      ↓
feed.start()        → HTTPAsyncConn/WSAsyncConn → ProxyResolver.resolve() → Proxied Connection
```

**Key Insight**: Proxy injection happens at the connection creation layer, before any exchange-specific logic executes.

## Core Components

### 1. ProxyResolver (Singleton)

**Purpose**: Central proxy resolution system that works transparently for all connection types.

```python
from typing import Optional, Dict, Protocol
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class ProxyConfig:
    """Immutable proxy configuration."""
    url: str
    type: str  # 'http', 'socks5', 'socks4'
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30

class ProxyManagerPlugin(Protocol):
    """Plugin interface for external proxy managers."""
    
    async def resolve_proxy(self, exchange_id: str, connection_type: str, 
                          region: Optional[str] = None) -> Optional[ProxyConfig]:
        """Resolve proxy configuration for exchange and connection type."""
        ...
    
    async def health_check(self, proxy_config: ProxyConfig) -> bool:
        """Check if proxy is healthy and responsive."""
        ...

class ProxyResolver:
    """Singleton proxy resolver with transparent injection capability."""
    
    _instance: Optional['ProxyResolver'] = None
    
    def __init__(self):
        self.config = {}
        self.plugins: List[ProxyManagerPlugin] = []
        self.cache = {}  # TTL cache for resolved proxies
    
    @classmethod
    def instance(cls) -> 'ProxyResolver':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    async def resolve(self, exchange_id: str, connection_type: str) -> Optional[ProxyConfig]:
        """Transparently resolve proxy configuration."""
        # 1. Check external plugins first
        for plugin in self.plugins:
            config = await plugin.resolve_proxy(exchange_id, connection_type)
            if config:
                return config
        
        # 2. Check exchange-specific configuration
        if exchange_id in self.config.get('exchanges', {}):
            proxy_url = self.config['exchanges'][exchange_id].get(connection_type)
            if proxy_url:
                return ProxyConfig(url=proxy_url, type=self._detect_proxy_type(proxy_url))
        
        # 3. Check default configuration
        default_config = self.config.get('default', {})
        proxy_url = default_config.get(connection_type)
        if proxy_url:
            return ProxyConfig(url=proxy_url, type=self._detect_proxy_type(proxy_url))
        
        # 4. Check regional auto-detection
        if self.config.get('regional', {}).get('enabled'):
            return await self._resolve_regional_proxy(exchange_id, connection_type)
        
        return None
```

### 2. Transparent Connection Mixins

**Purpose**: Add transparent proxy support to existing connection classes without breaking changes.

```python
class TransparentProxyMixin:
    """Mixin for transparent proxy injection into any connection type."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exchange_id = getattr(self, 'exchange_id', 'unknown')
    
    async def _inject_proxy_if_configured(self, session_or_client, connection_type: str):
        """Transparently inject proxy settings if configured."""
        proxy_config = await ProxyResolver.instance().resolve(
            self.exchange_id, 
            connection_type
        )
        
        if proxy_config:
            await self._apply_proxy_config(session_or_client, proxy_config)
            logger.info(f"Applied {proxy_config.type} proxy for {self.exchange_id} {connection_type}")
    
    async def _apply_proxy_config(self, session_or_client, proxy_config: ProxyConfig):
        """Apply proxy configuration to the specific client type."""
        # Implementation varies by client type (aiohttp, ccxt, websockets, etc.)
        raise NotImplementedError("Subclasses must implement proxy application")
```

### 3. Enhanced Connection Classes

**HTTP Connections**:
```python
class ProxyAwareHTTPAsyncConn(TransparentProxyMixin, HTTPAsyncConn):
    """Drop-in replacement for HTTPAsyncConn with transparent proxy support."""
    
    async def _create_session(self):
        """Create HTTP session with transparent proxy injection."""
        # Call original session creation
        session = await super()._create_session()
        
        # Transparently inject proxy if configured
        await self._inject_proxy_if_configured(session, 'rest')
        
        return session
    
    async def _apply_proxy_config(self, session: aiohttp.ClientSession, 
                                proxy_config: ProxyConfig):
        """Apply proxy to aiohttp session."""
        connector = aiohttp.ProxyConnector(
            proxy_url=proxy_config.url,
            proxy_auth=aiohttp.BasicAuth(
                proxy_config.username, 
                proxy_config.password
            ) if proxy_config.username else None
        )
        session._connector = connector
```

**WebSocket Connections**:
```python
class ProxyAwareWSAsyncConn(TransparentProxyMixin, WSAsyncConn):
    """Drop-in replacement for WSAsyncConn with transparent proxy support."""
    
    async def _connect(self, url: str):
        """Connect with transparent proxy injection."""
        proxy_config = await ProxyResolver.instance().resolve(self.exchange_id, 'websocket')
        
        if proxy_config:
            return await self._connect_via_proxy(url, proxy_config)
        else:
            return await super()._connect(url)
    
    async def _connect_via_proxy(self, url: str, proxy_config: ProxyConfig):
        """Connect via proxy (implementation depends on WebSocket library)."""
        # Use python-socks or similar for SOCKS proxy support
        if proxy_config.type.startswith('socks'):
            proxy = ProxyType.SOCKS5 if proxy_config.type == 'socks5' else ProxyType.SOCKS4
            return await websockets.connect(
                url,
                proxy_type=proxy,
                proxy_host=proxy_config.host,
                proxy_port=proxy_config.port,
                proxy_username=proxy_config.username,
                proxy_password=proxy_config.password
            )
        else:
            # HTTP proxy support
            return await websockets.connect(
                url,
                extra_headers={'Proxy-Authorization': f'Basic {proxy_config.auth_header}'}
            )
```

**CCXT Connections**:
```python
class ProxyAwareCcxtTransport(TransparentProxyMixin, CcxtRestTransport):
    """Transparent proxy injection for CCXT clients."""
    
    async def _create_client(self):
        """Create CCXT client with transparent proxy injection."""
        client = await super()._create_client()
        
        # Transparently inject proxy if configured
        await self._inject_proxy_if_configured(client, 'rest')
        
        return client
    
    async def _apply_proxy_config(self, client, proxy_config: ProxyConfig):
        """Apply proxy to CCXT client."""
        client.proxies = {
            'http': proxy_config.url,
            'https': proxy_config.url
        }
        
        # Also configure for ccxt.pro WebSocket
        client.options.update({
            'ws_proxy': proxy_config.url
        })
```

## Configuration Schema

### Comprehensive YAML Configuration

```yaml
# Transparent proxy injection configuration
proxy:
  # Global settings
  enabled: true
  auto_inject: true  # Automatically inject based on rules below
  
  # Default proxy settings (applied to all exchanges unless overridden)
  default:
    rest: socks5://proxy.company.com:1080
    websocket: socks5://proxy.company.com:1081
    timeout: 30
    
  # Exchange-specific proxy overrides
  exchanges:
    binance:
      rest: http://binance-proxy.company.com:8080
      websocket: socks5://binance-ws.company.com:1081
    
    backpack:
      rest: socks5://backpack-proxy.company.com:1080
      # websocket will use default
    
    # CCXT exchanges
    kraken:
      rest: http://kraken-proxy.company.com:8080
      websocket: socks5://kraken-ws.company.com:1081
  
  # Regional auto-detection and compliance
  regional:
    enabled: true
    detection_method: "geoip"  # or "manual"
    
    # Automatic proxy rules based on detected region
    rules:
      - regions: ["US", "CA"]
        exchanges: ["binance", "huobi"]
        proxy: "socks5://us-compliance-proxy.company.com:1080"
        
      - regions: ["CN"]
        exchanges: ["*"]  # All exchanges
        proxy: "socks5://china-proxy.company.com:1080"
        
      - regions: ["EU"]
        exchanges: ["binance"]
        proxy: "http://eu-binance-proxy.company.com:8080"
    
    # Fallback for blocked regions
    fallback_proxy: "socks5://global-fallback.company.com:1080"
  
  # External proxy manager integration
  manager:
    enabled: true
    plugin: "my_company.proxy_manager.K8sProxyManager"
    config:
      namespace: "trading-proxies"
      service_account: "cryptofeed-sa"
      refresh_interval: 300  # seconds
      health_check_interval: 60
    
    # Fallback to static config if manager fails
    fallback_to_static: true
  
  # Proxy health monitoring
  health_check:
    enabled: true
    interval: 120  # seconds
    timeout: 10
    retry_failed_after: 300  # seconds
    
    # Test endpoints for proxy validation
    test_endpoints:
      rest: "https://httpbin.org/ip"
      websocket: "wss://echo.websocket.org"
  
  # Logging and monitoring
  logging:
    level: "INFO"
    log_proxy_usage: true
    log_credentials: false  # Never log credentials
    metrics_enabled: true

# Standard exchange configuration (NO CHANGES REQUIRED)
exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    # No proxy configuration needed here!
    
  backpack:
    exchange_class: CcxtFeed
    exchange_id: backpack
    symbols: ["BTC-USDT"]
    channels: [TRADES]
    # Proxy automatically applied based on global config!
```

## Implementation Strategy

### Phase 1: Zero-Impact Infrastructure Setup

**Week 1**: Infrastructure components with no impact on existing code

1. **ProxyResolver Implementation**
   ```python
   # New files - no existing code modified
   cryptofeed/proxy/resolver.py
   cryptofeed/proxy/config.py
   cryptofeed/proxy/plugins.py
   ```

2. **Enhanced Connection Classes**
   ```python
   # New proxy-aware classes - existing classes unchanged
   cryptofeed/connection/proxy_http.py
   cryptofeed/connection/proxy_ws.py
   cryptofeed/connection/proxy_ccxt.py
   ```

3. **Configuration System**
   ```python
   # Enhanced config loading - backward compatible
   cryptofeed/config.py  # Add proxy config loading
   ```

### Phase 2: Transparent Integration

**Week 2**: Seamless integration with zero code changes required

1. **Connection Factory Updates**
   ```python
   # Modify connection factories to use proxy-aware classes
   # when proxy configuration is detected
   
   def create_http_connection(exchange_id, ...):
       if ProxyResolver.instance().has_config(exchange_id):
           return ProxyAwareHTTPAsyncConn(exchange_id, ...)
       else:
           return HTTPAsyncConn(...)  # Existing behavior
   ```

2. **Exchange Integration**
   ```python
   # NO CHANGES to existing exchange code
   # Proxy injection happens transparently at connection level
   
   # This continues to work exactly as before:
   feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
   ```

3. **CCXT Enhancement**
   ```python
   # Update CcxtGenericFeed to use proxy-aware transports
   # when proxy configuration is detected
   ```

### Phase 3: Advanced Features

**Week 3**: Advanced proxy management features

1. **External Manager Integration**
   - Kubernetes service mesh integration
   - Dynamic proxy rotation
   - Health checking and failover

2. **Regional Compliance**
   - Automatic region detection
   - Compliance rule engine
   - Blocked region handling

3. **Monitoring and Observability**
   - Proxy usage metrics
   - Performance monitoring
   - Health dashboards

## Testing Strategy

### 1. Backward Compatibility Tests

**Guarantee**: All existing code continues to work without modification

```python
def test_existing_exchanges_unchanged():
    """Test that existing exchanges work identically with proxy system enabled."""
    # Test with proxy config disabled
    feed_no_proxy = Binance(symbols=['BTC-USDT'], channels=[TRADES])
    
    # Test with proxy config enabled but not applicable
    feed_with_proxy_system = Binance(symbols=['BTC-USDT'], channels=[TRADES])
    
    # Both should behave identically
    assert feed_no_proxy.config == feed_with_proxy_system.config
```

### 2. Transparent Injection Tests

```python
def test_transparent_proxy_injection():
    """Test that proxies are transparently applied when configured."""
    # Configure proxy for binance
    ProxyResolver.instance().config = {
        'exchanges': {
            'binance': {
                'rest': 'socks5://test-proxy:1080'
            }
        }
    }
    
    # Create feed normally - no code changes
    feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
    
    # Proxy should be automatically applied
    assert feed.http_conn.proxy_config is not None
    assert feed.http_conn.proxy_config.url == 'socks5://test-proxy:1080'
```

### 3. Integration Tests

```python
def test_end_to_end_proxy_flow():
    """Test complete proxy flow with real proxy server."""
    # Start test proxy server
    with TestProxyServer() as proxy:
        # Configure cryptofeed to use test proxy
        config = {
            'proxy': {
                'default': {
                    'rest': f'http://localhost:{proxy.port}'
                }
            },
            'exchanges': {
                'binance': {
                    'symbols': ['BTC-USDT'],
                    'channels': [TRADES]
                }
            }
        }
        
        # Feed should work through proxy transparently
        feed = create_feed_from_config(config)
        await feed.start()
        
        # Verify traffic went through proxy
        assert proxy.request_count > 0
```

## Benefits of Transparent Injection

### 1. Zero Code Changes Required
- **Existing exchanges**: Work identically with or without proxies
- **User code**: No modifications needed for proxy support
- **Configuration-driven**: All proxy behavior controlled by YAML config

### 2. Universal Coverage
- **All connection types**: HTTP, WebSocket, CCXT clients
- **All exchanges**: Native and CCXT-based exchanges
- **All protocols**: SOCKS4, SOCKS5, HTTP proxies

### 3. Enterprise-Ready Features
- **External proxy managers**: Plugin system for enterprise integration
- **Regional compliance**: Automatic proxy application based on region
- **Health monitoring**: Automatic failover and proxy health checking
- **Observability**: Comprehensive logging and metrics

### 4. Production Reliability
- **Graceful fallback**: Direct connection if proxy fails
- **Performance monitoring**: Track proxy overhead and performance
- **Security**: Never log credentials, secure proxy configuration

## Success Metrics

- ✅ **Zero Breaking Changes**: 100% backward compatibility with existing code
- ✅ **Universal Coverage**: Works with all connection types (HTTP, WS, CCXT)
- ✅ **Regional Compliance**: Automatic proxy application for blocked regions
- ✅ **Performance**: <5% overhead for proxy-enabled connections
- ✅ **Enterprise Integration**: Plugin system for external proxy managers
- ✅ **Reliability**: >99.9% connection success rate with proxy failover

**Result**: Cryptofeed gains enterprise-grade proxy support with zero impact on existing code or users.