# Proxy Configuration Examples and Usage Patterns

## Overview

This document provides comprehensive examples of proxy configuration patterns for the cryptofeed proxy system. All examples use Pydantic v2 for type-safe configuration.

## Basic Configuration Patterns

### 1. Simple HTTP Proxy for All Exchanges

**Environment Variables:**
```bash
export CRYPTOFEED_PROXY_ENABLED=true
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="http://proxy.example.com:8080"
export CRYPTOFEED_PROXY_DEFAULT__HTTP__TIMEOUT_SECONDS=30
```

**YAML Configuration:**
```yaml
# config.yaml
proxy:
  enabled: true
  default:
    http:
      url: "http://proxy.example.com:8080"
      timeout_seconds: 30
```

**Python Configuration:**
```python
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies, init_proxy_system

settings = ProxySettings(
    enabled=True,
    default=ConnectionProxies(
        http=ProxyConfig(url="http://proxy.example.com:8080", timeout_seconds=30)
    )
)

init_proxy_system(settings)

# All HTTP connections now use proxy automatically
feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
feed.start()  # Uses proxy transparently
```

### 2. SOCKS5 Proxy for All Connections

**Environment Variables:**
```bash
export CRYPTOFEED_PROXY_ENABLED=true
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://user:pass@proxy.example.com:1080"
export CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL="socks5://user:pass@proxy.example.com:1081"
```

**YAML Configuration:**
```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://user:pass@proxy.example.com:1080"
      timeout_seconds: 30
    websocket:
      url: "socks5://user:pass@proxy.example.com:1081"
      timeout_seconds: 30
```

**Python Configuration:**
```python
settings = ProxySettings(
    enabled=True,
    default=ConnectionProxies(
        http=ProxyConfig(url="socks5://user:pass@proxy.example.com:1080"),
        websocket=ProxyConfig(url="socks5://user:pass@proxy.example.com:1081")
    )
)

init_proxy_system(settings)

# Both HTTP and WebSocket connections use SOCKS5 proxy
feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
feed.start()
```

### 3. Per-Exchange Proxy Configuration

**Environment Variables:**
```bash
# Enable proxy system
export CRYPTOFEED_PROXY_ENABLED=true

# Default proxy for most exchanges
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://default-proxy:1080"
export CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL="socks5://default-proxy:1081"

# Binance-specific proxy
export CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL="http://binance-proxy:8080"
export CRYPTOFEED_PROXY_EXCHANGES__BINANCE__WEBSOCKET__URL="socks5://binance-proxy:1081"

# Coinbase-specific proxy
export CRYPTOFEED_PROXY_EXCHANGES__COINBASE__HTTP__URL="http://coinbase-proxy:8080"
# Coinbase WebSocket uses default proxy
```

**YAML Configuration:**
```yaml
proxy:
  enabled: true
  
  # Default proxy for all exchanges
  default:
    http:
      url: "socks5://default-proxy:1080"
      timeout_seconds: 30
    websocket:
      url: "socks5://default-proxy:1081"
      timeout_seconds: 30
  
  # Exchange-specific overrides
  exchanges:
    binance:
      http:
        url: "http://binance-proxy:8080"
        timeout_seconds: 15
      websocket:
        url: "socks5://binance-proxy:1081"
        timeout_seconds: 15
    
    coinbase:
      http:
        url: "http://coinbase-proxy:8080"
        timeout_seconds: 10
      # websocket: null (uses default)
    
    backpack:
      # Only override WebSocket proxy
      websocket:
        url: "socks5://backpack-proxy:1080"
        timeout_seconds: 20
      # http: null (uses default)
```

**Python Configuration:**
```python
settings = ProxySettings(
    enabled=True,
    default=ConnectionProxies(
        http=ProxyConfig(url="socks5://default-proxy:1080"),
        websocket=ProxyConfig(url="socks5://default-proxy:1081")
    ),
    exchanges={
        "binance": ConnectionProxies(
            http=ProxyConfig(url="http://binance-proxy:8080", timeout_seconds=15),
            websocket=ProxyConfig(url="socks5://binance-proxy:1081", timeout_seconds=15)
        ),
        "coinbase": ConnectionProxies(
            http=ProxyConfig(url="http://coinbase-proxy:8080", timeout_seconds=10)
            # websocket uses default
        ),
        "backpack": ConnectionProxies(
            # http uses default
            websocket=ProxyConfig(url="socks5://backpack-proxy:1080", timeout_seconds=20)
        )
    }
)

init_proxy_system(settings)

# Each exchange uses its specific proxy configuration
binance_feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])  # Uses binance-proxy
coinbase_feed = Coinbase(symbols=['BTC-USD'], channels=[TRADES])  # Uses coinbase-proxy for HTTP, default for WebSocket
backpack_feed = CcxtFeed(exchange_id="backpack", symbols=['SOL-USDT'], channels=[TRADES])  # Uses default for HTTP, backpack-proxy for WebSocket
```

## Production Environment Patterns

### 4. Corporate Environment with Regional Proxies

**YAML Configuration:**
```yaml
# production-config.yaml
proxy:
  enabled: true
  
  # Global corporate proxy as default
  default:
    http:
      url: "socks5://corporate-proxy.company.com:1080"
      timeout_seconds: 30
    websocket:
      url: "socks5://corporate-proxy.company.com:1081"
      timeout_seconds: 30
  
  exchanges:
    # US exchanges through US proxy
    coinbase:
      http:
        url: "http://proxy-us.company.com:8080"
        timeout_seconds: 15
      websocket:
        url: "socks5://proxy-us.company.com:1081"
        timeout_seconds: 15
    
    kraken:
      http:
        url: "http://proxy-us.company.com:8080"
        timeout_seconds: 15
      websocket:
        url: "socks5://proxy-us.company.com:1081"
        timeout_seconds: 15
    
    # Asian exchanges through Asian proxy
    binance:
      http:
        url: "http://proxy-asia.company.com:8080"
        timeout_seconds: 20
      websocket:
        url: "socks5://proxy-asia.company.com:1081"
        timeout_seconds: 20
    
    backpack:
      http:
        url: "http://proxy-asia.company.com:8080"
        timeout_seconds: 20
      websocket:
        url: "socks5://proxy-asia.company.com:1081"
        timeout_seconds: 20
    
    # European exchanges through European proxy
    bitstamp:
      http:
        url: "http://proxy-eu.company.com:8080"
        timeout_seconds: 25
      websocket:
        url: "socks5://proxy-eu.company.com:1081"
        timeout_seconds: 25
```

**Usage:**
```python
# Load configuration from YAML file
import yaml
from cryptofeed.proxy import ProxySettings, init_proxy_system

with open('production-config.yaml', 'r') as f:
    config = yaml.safe_load(f)

settings = ProxySettings(**config['proxy'])
init_proxy_system(settings)

# Start feeds - proxy routing is automatic based on exchange
us_feeds = [
    Coinbase(symbols=['BTC-USD'], channels=[TRADES]),
    Kraken(symbols=['BTC-USD'], channels=[TRADES])
]

asian_feeds = [
    Binance(symbols=['BTC-USDT'], channels=[TRADES]),
    CcxtFeed(exchange_id="backpack", symbols=['SOL-USDT'], channels=[TRADES])
]

european_feeds = [
    Bitstamp(symbols=['BTC-EUR'], channels=[TRADES])
]

# All feeds use appropriate regional proxies automatically
for feed in us_feeds + asian_feeds + european_feeds:
    feed.start()
```

### 5. High-Frequency Trading Environment

**YAML Configuration:**
```yaml
# hft-config.yaml
proxy:
  enabled: true
  
  # Low-latency default proxy
  default:
    http:
      url: "socks5://fast-proxy.hft.com:1080"
      timeout_seconds: 5  # Aggressive timeout for HFT
    websocket:
      url: "socks5://fast-proxy.hft.com:1081"
      timeout_seconds: 5
  
  exchanges:
    # Exchange-specific low-latency proxies
    binance:
      http:
        url: "socks5://binance-direct.hft.com:1080"
        timeout_seconds: 3  # Ultra-low timeout
      websocket:
        url: "socks5://binance-direct.hft.com:1081"
        timeout_seconds: 3
    
    coinbase:
      http:
        url: "socks5://coinbase-direct.hft.com:1080"
        timeout_seconds: 3
      websocket:
        url: "socks5://coinbase-direct.hft.com:1081"
        timeout_seconds: 3
    
    backpack:
      http:
        url: "socks5://backpack-direct.hft.com:1080"
        timeout_seconds: 4
      websocket:
        url: "socks5://backpack-direct.hft.com:1081"
        timeout_seconds: 4
```

**Usage:**
```python
# HFT application with low-latency proxy configuration
import yaml
from cryptofeed.proxy import ProxySettings, init_proxy_system

# Load HFT proxy configuration
with open('hft-config.yaml', 'r') as f:
    config = yaml.safe_load(f)

settings = ProxySettings(**config['proxy'])
init_proxy_system(settings)

# Start high-frequency feeds with optimized proxy routing
hft_feeds = [
    Binance(symbols=['BTC-USDT', 'ETH-USDT'], channels=[TRADES, L2_BOOK]),
    Coinbase(symbols=['BTC-USD', 'ETH-USD'], channels=[TRADES, L2_BOOK]),
    CcxtFeed(exchange_id="backpack", symbols=['SOL-USDT'], channels=[TRADES])
]

for feed in hft_feeds:
    feed.start()
```

### 6. Development Environment

**Local Development:**
```yaml
# dev-config.yaml
proxy:
  enabled: true
  
  # Local development proxy (e.g., running on localhost)
  default:
    http:
      url: "http://localhost:8888"  # Local proxy for development
      timeout_seconds: 60  # Generous timeout for debugging
    websocket:
      url: "socks5://localhost:1080"
      timeout_seconds: 60

# No exchange-specific overrides in development
```

**Testing Environment:**
```yaml
# test-config.yaml  
proxy:
  enabled: true
  
  # Test proxy server
  default:
    http:
      url: "http://test-proxy.internal:8080"
      timeout_seconds: 45
    websocket:
      url: "socks5://test-proxy.internal:1081"
      timeout_seconds: 45
  
  # Test exchange overrides
  exchanges:
    binance:
      http:
        url: "http://binance-test-proxy.internal:8080"
        timeout_seconds: 30
```

## Advanced Configuration Patterns

### 7. Mixed Proxy Types

**YAML Configuration:**
```yaml
proxy:
  enabled: true
  
  # SOCKS5 as default
  default:
    http:
      url: "socks5://socks-proxy.example.com:1080"
      timeout_seconds: 30
    websocket:
      url: "socks5://socks-proxy.example.com:1081"
      timeout_seconds: 30
  
  exchanges:
    # HTTP proxy for specific exchange
    coinbase:
      http:
        url: "http://http-proxy.example.com:8080"
        timeout_seconds: 20
      # websocket uses default SOCKS5
    
    # HTTPS proxy for secure connection
    kraken:
      http:
        url: "https://secure-proxy.example.com:8443"
        timeout_seconds: 25
    
    # Different SOCKS proxy for specific exchange
    binance:
      http:
        url: "socks4://socks4-proxy.example.com:1080"
        timeout_seconds: 15
      websocket:
        url: "socks5://socks5-proxy.example.com:1081"
        timeout_seconds: 15
```

### 8. Conditional Proxy Configuration

**Python Configuration with Environment Detection:**
```python
import os
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies, init_proxy_system

def get_proxy_settings():
    """Get proxy settings based on environment."""
    environment = os.getenv('ENVIRONMENT', 'development')
    
    if environment == 'production':
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://prod-proxy.company.com:1080"),
                websocket=ProxyConfig(url="socks5://prod-proxy.company.com:1081")
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://binance-prod.company.com:8080", timeout_seconds=10)
                )
            }
        )
    elif environment == 'staging':
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="http://staging-proxy.company.com:8080"),
                websocket=ProxyConfig(url="socks5://staging-proxy.company.com:1081")
            )
        )
    elif environment == 'testing':
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="http://test-proxy.internal:8080", timeout_seconds=60)
            )
        )
    else:  # development
        return ProxySettings(
            enabled=False  # Direct connections in development
        )

# Initialize proxy system based on environment
settings = get_proxy_settings()
init_proxy_system(settings)

# Start feeds - proxy configuration depends on environment
feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
feed.start()
```

### 9. Docker/Container Environment

**Docker Compose with Proxy:**
```yaml
# docker-compose.yml
version: '3.8'

services:
  cryptofeed:
    image: cryptofeed:latest
    environment:
      # Proxy configuration via environment variables
      - CRYPTOFEED_PROXY_ENABLED=true
      - CRYPTOFEED_PROXY_DEFAULT__HTTP__URL=socks5://proxy-container:1080
      - CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL=socks5://proxy-container:1081
      - CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL=http://binance-proxy:8080
    depends_on:
      - proxy-container
      - binance-proxy
    networks:
      - crypto-network

  proxy-container:
    image: serjs/go-socks5-proxy
    ports:
      - "1080:1080"
      - "1081:1081"
    networks:
      - crypto-network

  binance-proxy:
    image: nginx:alpine
    ports:
      - "8080:8080"
    networks:
      - crypto-network

networks:
  crypto-network:
    driver: bridge
```

**Kubernetes ConfigMap:**
```yaml
# proxy-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cryptofeed-proxy-config
data:
  config.yaml: |
    proxy:
      enabled: true
      default:
        http:
          url: "socks5://proxy-service.default.svc.cluster.local:1080"
          timeout_seconds: 30
        websocket:
          url: "socks5://proxy-service.default.svc.cluster.local:1081"
          timeout_seconds: 30
      exchanges:
        binance:
          http:
            url: "http://binance-proxy-service.default.svc.cluster.local:8080"
            timeout_seconds: 15
```

## Configuration Validation Examples

### 10. Configuration with Validation

**Python with Validation:**
```python
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies
from pydantic import ValidationError

def create_validated_proxy_config():
    """Create proxy configuration with comprehensive validation."""
    try:
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(
                    url="socks5://proxy.example.com:1080",
                    timeout_seconds=30
                ),
                websocket=ProxyConfig(
                    url="socks5://proxy.example.com:1081", 
                    timeout_seconds=30
                )
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(
                        url="http://binance-proxy.example.com:8080",
                        timeout_seconds=15
                    )
                )
            }
        )
        
        # Validate that we can get proxy configurations
        assert settings.get_proxy("binance", "http") is not None
        assert settings.get_proxy("binance", "websocket") is not None  # Should use default
        assert settings.get_proxy("unknown_exchange", "http") is not None  # Should use default
        
        return settings
        
    except ValidationError as e:
        print(f"Configuration validation failed: {e}")
        raise
    except AssertionError as e:
        print(f"Configuration logic validation failed: {e}")
        raise

# Use validated configuration
settings = create_validated_proxy_config()
init_proxy_system(settings)
```

**Configuration Testing:**
```python
import pytest
from cryptofeed.proxy import ProxySettings, ProxyConfig

def test_proxy_url_validation():
    """Test proxy URL validation."""
    # Valid URLs
    ProxyConfig(url="http://proxy:8080")
    ProxyConfig(url="https://proxy:8443")
    ProxyConfig(url="socks4://proxy:1080")
    ProxyConfig(url="socks5://user:pass@proxy:1080")
    
    # Invalid URLs should raise ValidationError
    with pytest.raises(ValueError):
        ProxyConfig(url="invalid-url")
    
    with pytest.raises(ValueError):
        ProxyConfig(url="ftp://proxy:21")  # Unsupported scheme
    
    with pytest.raises(ValueError):
        ProxyConfig(url="socks5://proxy")  # Missing port

def test_timeout_validation():
    """Test timeout validation."""
    # Valid timeouts
    ProxyConfig(url="socks5://proxy:1080", timeout_seconds=1)
    ProxyConfig(url="socks5://proxy:1080", timeout_seconds=300)
    
    # Invalid timeouts
    with pytest.raises(ValueError):
        ProxyConfig(url="socks5://proxy:1080", timeout_seconds=0)
    
    with pytest.raises(ValueError):
        ProxyConfig(url="socks5://proxy:1080", timeout_seconds=301)
```

## Troubleshooting Common Configurations

### 11. Debugging Proxy Configuration

**Environment Variable Debugging:**
```bash
# Check if environment variables are set correctly
env | grep CRYPTOFEED_PROXY

# Expected output:
# CRYPTOFEED_PROXY_ENABLED=true
# CRYPTOFEED_PROXY_DEFAULT__HTTP__URL=socks5://proxy:1080
# CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL=http://binance-proxy:8080
```

**Python Debugging:**
```python
from cryptofeed.proxy import load_proxy_settings, get_proxy_injector

# Load and inspect settings
settings = load_proxy_settings()
print(f"Proxy enabled: {settings.enabled}")
print(f"Default HTTP proxy: {settings.default.http if settings.default else None}")
print(f"Exchange overrides: {list(settings.exchanges.keys())}")

# Check if proxy injector is initialized
injector = get_proxy_injector()
if injector:
    print("Proxy injector is active")
    print(f"Binance HTTP proxy: {injector.get_http_proxy_url('binance')}")
    print(f"Coinbase HTTP proxy: {injector.get_http_proxy_url('coinbase')}")
else:
    print("Proxy injector is not active")
```

**Connection Testing:**
```python
import asyncio
from cryptofeed.connection import HTTPAsyncConn
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies, init_proxy_system

async def test_proxy_connection():
    """Test that proxy is actually being used."""
    # Configure proxy
    settings = ProxySettings(
        enabled=True,
        default=ConnectionProxies(
            http=ProxyConfig(url="http://proxy.example.com:8080")
        )
    )
    init_proxy_system(settings)
    
    # Create connection with exchange_id
    conn = HTTPAsyncConn("test", exchange_id="binance")
    
    try:
        await conn._open()
        print("Connection opened successfully with proxy")
        print(f"Session proxy: {getattr(conn.conn, '_proxy', 'None')}")
    finally:
        if conn.is_open:
            await conn.close()

# Run test
asyncio.run(test_proxy_connection())
```

## Best Practices

### 12. Configuration Best Practices

1. **Use Environment Variables for Credentials:**
```bash
# Good - credentials in environment
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://user:${PROXY_PASSWORD}@proxy:1080"

# Bad - credentials in config files
# url: "socks5://user:password123@proxy:1080"  # Don't do this
```

2. **Use Different Timeouts for Different Environments:**
```yaml
# Production - aggressive timeouts
proxy:
  enabled: true
  default:
    http:
      url: "socks5://proxy:1080"
      timeout_seconds: 10  # Fast fail in production

# Development - generous timeouts  
proxy:
  enabled: true
  default:
    http:
      url: "http://localhost:8888"
      timeout_seconds: 60  # Allow debugging time
```

3. **Validate Configuration at Startup:**
```python
def validate_proxy_configuration():
    """Validate proxy configuration at application startup."""
    settings = load_proxy_settings()
    
    if not settings.enabled:
        print("Proxy system disabled")
        return
    
    # Test basic configuration
    if settings.default:
        print(f"Default HTTP proxy: {settings.default.http.url if settings.default.http else 'None'}")
        print(f"Default WebSocket proxy: {settings.default.websocket.url if settings.default.websocket else 'None'}")
    
    # Test exchange overrides
    for exchange_id, proxies in settings.exchanges.items():
        print(f"{exchange_id}: HTTP={proxies.http.url if proxies.http else 'default'}, "
              f"WebSocket={proxies.websocket.url if proxies.websocket else 'default'}")

# Call at application startup
validate_proxy_configuration()
```

4. **Use Configuration Files for Complex Setups:**
```python
# Good for complex configurations
import yaml
from cryptofeed.proxy import ProxySettings

with open('proxy-config.yaml', 'r') as f:
    config = yaml.safe_load(f)

settings = ProxySettings(**config['proxy'])
```

5. **Test Proxy Configuration in Staging:**
```python
# Test proxy configuration before production deployment
async def test_all_exchange_proxies():
    """Test that all configured exchanges can connect through proxies."""
    settings = load_proxy_settings()
    exchanges = ['binance', 'coinbase', 'backpack'] + list(settings.exchanges.keys())
    
    for exchange_id in exchanges:
        http_proxy = settings.get_proxy(exchange_id, 'http')
        ws_proxy = settings.get_proxy(exchange_id, 'websocket')
        
        print(f"{exchange_id}: HTTP={http_proxy.url if http_proxy else 'direct'}, "
              f"WebSocket={ws_proxy.url if ws_proxy else 'direct'}")
        
        # Test actual connectivity (implementation depends on your testing needs)
        # await test_exchange_connectivity(exchange_id)

asyncio.run(test_all_exchange_proxies())
```

This comprehensive guide covers all major proxy configuration patterns and use cases for the cryptofeed proxy system, providing both simple examples for getting started and complex patterns for production environments.