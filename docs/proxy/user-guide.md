# Proxy System User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration Methods](#configuration-methods)
3. [Common Patterns](#common-patterns)
4. [Production Environments](#production-environments)
5. [Troubleshooting](#troubleshooting)
6. [Best Practices](#best-practices)

## Getting Started

The cryptofeed proxy system allows routing all exchange connections through HTTP or SOCKS proxies with zero code changes to your existing applications.

### Basic Concepts

- **Transparent**: Existing code works without modifications
- **Per-Exchange**: Different proxies for different exchanges
- **Type-Safe**: Full Pydantic v2 validation of all configuration
- **Fallback**: Exchange-specific overrides with default fallback

### Minimal Example

**Step 1: Enable Proxy**
```bash
export CRYPTOFEED_PROXY_ENABLED=true
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://proxy.example.com:1080"
```

**Step 2: Run Existing Code**
```python
# This code doesn't change at all
feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
feed.start()  # Now automatically uses proxy
```

That's it! Your existing cryptofeed applications now route through the proxy.

### Initialization Precedence

`FeedHandler` automatically initializes the proxy system on startup. Configuration precedence is:

1. **Environment variables** (`CRYPTOFEED_PROXY_*`) override all other sources.
2. **YAML configuration** (`proxy` block in `config.yaml`) is used when environment variables are absent.
3. **Programmatic settings** passed via `FeedHandler(proxy_settings=...)` act as the final fallback.

```python
from cryptofeed.feedhandler import FeedHandler
from cryptofeed.proxy import ProxySettings, ConnectionProxies, ProxyConfig

custom_proxy = ProxySettings(
    enabled=True,
    default=ConnectionProxies(
        http=ProxyConfig(url="http://code-proxy:8080")
    )
)

fh = FeedHandler(config="config.yaml", proxy_settings=custom_proxy)
# Environment variables will override config and custom_proxy if present.
```

## Configuration Methods

### 1. Environment Variables (Recommended for Docker/Kubernetes)

**Basic Configuration:**
```bash
# Enable proxy system
export CRYPTOFEED_PROXY_ENABLED=true

# Default HTTP proxy for all exchanges
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://proxy:1080"
export CRYPTOFEED_PROXY_DEFAULT__HTTP__TIMEOUT_SECONDS=30

# Default WebSocket proxy
export CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL="socks5://proxy:1081"

# Exchange-specific overrides
export CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL="http://binance-proxy:8080"
export CRYPTOFEED_PROXY_EXCHANGES__COINBASE__HTTP__URL="socks5://coinbase-proxy:1080"
```

**Variable Naming Pattern:**
```
CRYPTOFEED_PROXY_[SECTION]__[EXCHANGE]__[CONNECTION_TYPE]__[FIELD]
```

Examples:
- `CRYPTOFEED_PROXY_ENABLED` - Enable/disable proxy system
- `CRYPTOFEED_PROXY_DEFAULT__HTTP__URL` - Default HTTP proxy URL
- `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL` - Binance-specific HTTP proxy
- `CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__TIMEOUT_SECONDS` - Binance HTTP timeout

### 2. YAML Configuration (Recommended for Complex Setups)

**Basic YAML:**
```yaml
# config.yaml
proxy:
  enabled: true
  
  default:
    http:
      url: "socks5://proxy.example.com:1080"
      timeout_seconds: 30
    websocket:
      url: "socks5://proxy.example.com:1081"
      timeout_seconds: 30
  
  exchanges:
    binance:
      http:
        url: "http://binance-proxy:8080"
        timeout_seconds: 15
    coinbase:
      http:
        url: "socks5://coinbase-proxy:1080"
        timeout_seconds: 20
```

**Load YAML in Python:**
```python
import yaml
from cryptofeed.proxy import ProxySettings, init_proxy_system

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize proxy system
settings = ProxySettings(**config['proxy'])
init_proxy_system(settings)

# Your existing code now uses proxy
feed = Binance(symbols=['BTC-USDT'], channels=[TRADES])
feed.start()
```

### 3. Python Configuration (Recommended for Dynamic Setup)

```python
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies, init_proxy_system

# Programmatic configuration
settings = ProxySettings(
    enabled=True,
    default=ConnectionProxies(
        http=ProxyConfig(url="socks5://proxy:1080", timeout_seconds=30),
        websocket=ProxyConfig(url="socks5://proxy:1081", timeout_seconds=30)
    ),
    exchanges={
        "binance": ConnectionProxies(
            http=ProxyConfig(url="http://binance-proxy:8080", timeout_seconds=15)
        ),
        "coinbase": ConnectionProxies(
            http=ProxyConfig(url="socks5://coinbase-proxy:1080", timeout_seconds=20)
        )
    }
)

# Initialize proxy system
init_proxy_system(settings)

# Start your feeds
feeds = [
    Binance(symbols=['BTC-USDT'], channels=[TRADES]),      # Uses binance-proxy
    Coinbase(symbols=['BTC-USD'], channels=[TRADES]),      # Uses coinbase-proxy
    CcxtFeed(exchange_id="backpack", symbols=['SOL-USDT'], channels=[TRADES])  # Uses default proxy
]

for feed in feeds:
    feed.start()
```

## Deployment Examples

### Docker Compose

```yaml
services:
  cryptofeed:
    image: ghcr.io/cryptofeed/cryptofeed:latest
    environment:
      CRYPTOFEED_PROXY_ENABLED: "true"
      CRYPTOFEED_PROXY_DEFAULT__HTTP__URL: "socks5://proxy:1080"
      CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL: "socks5://proxy:1081"
      CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL: "http://binance-proxy:8080"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    command: ["python", "run_feeds.py", "--config", "config.yaml"]
```

### Kubernetes Deployment with ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cryptofeed-config
data:
  config.yaml: |
    proxy:
      enabled: true
      default:
        http:
          url: "socks5://proxy.internal:1080"
        websocket:
          url: "socks5://proxy.internal:1081"
      exchanges:
        coinbase:
          http:
            url: "http://coinbase-proxy.internal:8080"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cryptofeed
spec:
  replicas: 1
  selector:
    matchLabels:
      app: cryptofeed
  template:
    metadata:
      labels:
        app: cryptofeed
    spec:
      containers:
        - name: cryptofeed
          image: ghcr.io/cryptofeed/cryptofeed:latest
          env:
            - name: CRYPTOFEED_PROXY_ENABLED
              value: "true"
            - name: CRYPTOFEED_PROXY_DEFAULT__HTTP__URL
              value: "socks5://proxy.internal:1080"
          volumeMounts:
            - name: config
              mountPath: /app/config.yaml
              subPath: config.yaml
      volumes:
        - name: config
          configMap:
            name: cryptofeed-config
```

## Test Execution

### Recommended Pytest Commands

- Full proxy suite (unit + integration):
  ```bash
  pytest tests/unit/test_proxy_mvp.py tests/integration/test_proxy_http.py tests/integration/test_proxy_ws.py
  ```
- HTTP-only scenarios:
  ```bash
  pytest tests/integration/test_proxy_http.py -k "proxy"
  ```
- WebSocket-only scenarios (requires `python-socks` for SOCKS coverage):
  ```bash
  pytest tests/integration/test_proxy_ws.py
  ```

### Pytest Notes

- Async tests rely on `pytest-asyncio` strict mode.
- Logging assertions use helpers in `tests/util/proxy_assertions.py` to ensure credentials never surface.

### CI Matrix

The `cryptofeed tests` GitHub workflow runs the proxy suites twice per Python version:

- `python-socks=with` — installs `python-socks` to exercise SOCKS branches.
- `python-socks=without` — omits the dependency to confirm ImportError paths.

Workflow definition: `.github/workflows/tests.yml`.

## Common Patterns

### Pattern 1: Simple Corporate Proxy

**Use Case:** Route all traffic through single corporate proxy

```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://corporate-proxy.company.com:1080"
    websocket:
      url: "socks5://corporate-proxy.company.com:1081"
```

### Pattern 2: Exchange-Specific Proxies

**Use Case:** Different proxies for regulatory compliance or performance

```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://default-proxy:1080"
  
  exchanges:
    # US exchanges through US proxy
    coinbase:
      http:
        url: "http://us-proxy:8080"
    kraken:
      http:
        url: "http://us-proxy:8080"
    
    # Asian exchanges through Asian proxy
    binance:
      http:
        url: "socks5://asia-proxy:1080"
    backpack:
      http:
        url: "socks5://asia-proxy:1080"
```

### Pattern 3: Mixed Proxy Types

**Use Case:** Different proxy protocols for different requirements

```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://socks-proxy:1080"     # SOCKS5 as default
  
  exchanges:
    coinbase:
      http:
        url: "http://http-proxy:8080"      # HTTP for Coinbase
    binance:
      http:
        url: "socks4://socks4-proxy:1080"  # SOCKS4 for Binance
```

### Pattern 4: High-Performance Trading

**Use Case:** Low-latency proxies with aggressive timeouts

```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://fast-proxy:1080"
      timeout_seconds: 5  # Aggressive default timeout
  
  exchanges:
    binance:
      http:
        url: "socks5://binance-direct:1080"
        timeout_seconds: 3  # Ultra-low timeout for HFT
      websocket:
        url: "socks5://binance-direct:1081"
        timeout_seconds: 3
```

## Production Environments

### Docker Deployment

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  cryptofeed:
    image: cryptofeed:latest
    environment:
      - CRYPTOFEED_PROXY_ENABLED=true
      - CRYPTOFEED_PROXY_DEFAULT__HTTP__URL=socks5://proxy:1080
      - CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL=http://binance-proxy:8080
    depends_on:
      - proxy
      - binance-proxy

  proxy:
    image: serjs/go-socks5-proxy
    ports:
      - "1080:1080"

  binance-proxy:
    image: nginx:alpine
    ports:
      - "8080:8080"
```

### Kubernetes Deployment

**ConfigMap:**
```yaml
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
          url: "socks5://proxy-service:1080"
      exchanges:
        binance:
          http:
            url: "http://binance-proxy-service:8080"
```

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cryptofeed
spec:
  template:
    spec:
      containers:
      - name: cryptofeed
        image: cryptofeed:latest
        volumeMounts:
        - name: proxy-config
          mountPath: /config
        env:
        - name: CRYPTOFEED_CONFIG_FILE
          value: "/config/config.yaml"
      volumes:
      - name: proxy-config
        configMap:
          name: cryptofeed-proxy-config
```

### Environment-Specific Configuration

**Multi-Environment Setup:**
```python
import os
from cryptofeed.proxy import ProxySettings, ProxyConfig, ConnectionProxies

def get_proxy_settings():
    env = os.getenv('ENVIRONMENT', 'development')
    
    if env == 'production':
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://prod-proxy:1080", timeout_seconds=10)
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://binance-prod:8080", timeout_seconds=5)
                )
            }
        )
    elif env == 'staging':
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="http://staging-proxy:8080", timeout_seconds=30)
            )
        )
    else:  # development
        return ProxySettings(enabled=False)  # Direct connections

# Use environment-appropriate configuration
settings = get_proxy_settings()
init_proxy_system(settings)
```

## Troubleshooting

### Common Issues

**1. Proxy Not Being Used**

*Symptoms:* Connections go direct instead of through proxy

*Solutions:*
```bash
# Check if proxy is enabled
echo $CRYPTOFEED_PROXY_ENABLED  # Should be "true"

# Verify proxy URL format
echo $CRYPTOFEED_PROXY_DEFAULT__HTTP__URL  # Should include scheme and port
```

*Debug in Python:*
```python
from cryptofeed.proxy import load_proxy_settings, get_proxy_injector

settings = load_proxy_settings()
print(f"Enabled: {settings.enabled}")
print(f"Default HTTP: {settings.default.http.url if settings.default and settings.default.http else 'None'}")

injector = get_proxy_injector()
print(f"Injector active: {injector is not None}")
```

**2. WebSocket Proxy Failures**

*Symptoms:* HTTP works but WebSocket connections fail

*Solutions:*
```bash
# Install SOCKS proxy support
pip install python-socks

# Use SOCKS proxy for WebSocket
export CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL="socks5://proxy:1081"
```

**3. Configuration Not Loading**

*Symptoms:* Environment variables not being recognized

*Solutions:*
```bash
# Check variable naming (double underscores)
export CRYPTOFEED_PROXY_ENABLED=true                          # ✅ Correct
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://proxy:1080"  # ✅ Correct

export CRYPTOFEED_PROXY_DEFAULT_HTTP_URL="socks5://proxy:1080"    # ❌ Wrong (single underscore)
```

**4. Connection Timeouts**

*Symptoms:* Connections failing with timeout errors

*Solutions:*
```yaml
proxy:
  enabled: true
  default:
    http:
      url: "socks5://proxy:1080"
      timeout_seconds: 60  # Increase timeout
```

### Debug Mode

**Enable Debug Logging:**
```python
import logging
from cryptofeed.proxy import load_proxy_settings, init_proxy_system

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Load and inspect settings
settings = load_proxy_settings()
print(f"Settings: {settings}")

init_proxy_system(settings)

# Test proxy resolution
from cryptofeed.proxy import get_proxy_injector
injector = get_proxy_injector()
if injector:
    print(f"Binance HTTP proxy: {injector.get_http_proxy_url('binance')}")
    print(f"Coinbase HTTP proxy: {injector.get_http_proxy_url('coinbase')}")
```

**Test Connectivity:**
```python
import asyncio
from cryptofeed.connection import HTTPAsyncConn

async def test_proxy():
    conn = HTTPAsyncConn("test", exchange_id="binance")
    try:
        await conn._open()
        print("✅ Connection successful")
        # You can inspect conn.conn._proxy or other session details
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    finally:
        if conn.is_open:
            await conn.close()

asyncio.run(test_proxy())
```

## Best Practices

### Security

**1. Protect Credentials**
```bash
# ✅ Good - use environment variables for credentials
export PROXY_PASSWORD="secret123"
export CRYPTOFEED_PROXY_DEFAULT__HTTP__URL="socks5://user:${PROXY_PASSWORD}@proxy:1080"

# ❌ Bad - credentials in config files
# url: "socks5://user:secret123@proxy:1080"
```

**2. Use HTTPS/SOCKS5 for Sensitive Data**
```yaml
# ✅ Prefer encrypted protocols
proxy:
  default:
    http:
      url: "socks5://proxy:1080"  # SOCKS5 preferred
    # or
    # url: "https://proxy:8443"   # HTTPS acceptable
```

### Performance

**1. Environment-Appropriate Timeouts**
```yaml
# Production - aggressive timeouts
proxy:
  default:
    http:
      timeout_seconds: 10

# Development - generous timeouts for debugging
proxy:
  default:
    http:
      timeout_seconds: 60
```

**2. Exchange-Specific Optimization**
```yaml
proxy:
  exchanges:
    binance:
      http:
        url: "socks5://binance-optimized:1080"
        timeout_seconds: 3  # Fast proxy, low timeout
    coinbase:
      http:
        url: "http://coinbase-proxy:8080"
        timeout_seconds: 15  # Slower proxy, higher timeout
```

### Maintainability

**1. Use Configuration Files for Complex Setups**
```python
# ✅ Good for complex configurations
with open('proxy-config.yaml', 'r') as f:
    config = yaml.safe_load(f)
settings = ProxySettings(**config['proxy'])

# ❌ Avoid for complex setups
settings = ProxySettings(enabled=True, default=ConnectionProxies(...))  # Too verbose
```

**2. Validate Configuration at Startup**
```python
def validate_proxy_setup():
    """Validate proxy configuration at application startup."""
    settings = load_proxy_settings()
    
    if not settings.enabled:
        print("ℹ️  Proxy system disabled")
        return
    
    print("✅ Proxy system enabled")
    
    # Test each configured exchange
    exchanges = list(settings.exchanges.keys()) or ['binance', 'coinbase']
    for exchange in exchanges:
        http_proxy = settings.get_proxy(exchange, 'http')
        ws_proxy = settings.get_proxy(exchange, 'websocket')
        print(f"  {exchange}: HTTP={http_proxy.url if http_proxy else 'direct'}, "
              f"WS={ws_proxy.url if ws_proxy else 'direct'}")

# Call at application startup
validate_proxy_setup()
```

**3. Test Configuration in Staging**
```python
async def test_exchange_connectivity():
    """Test that all exchanges can connect through their configured proxies."""
    settings = load_proxy_settings()
    
    test_exchanges = ['binance', 'coinbase', 'backpack']
    
    for exchange_id in test_exchanges:
        conn = HTTPAsyncConn(f"test-{exchange_id}", exchange_id=exchange_id)
        try:
            await conn._open()
            print(f"✅ {exchange_id}: Connection successful")
        except Exception as e:
            print(f"❌ {exchange_id}: Connection failed - {e}")
        finally:
            if conn.is_open:
                await conn.close()

# Run connectivity tests in staging environment
# asyncio.run(test_exchange_connectivity())
```

### Monitoring

**1. Log Proxy Usage**
```python
import logging
from cryptofeed.proxy import get_proxy_injector

logger = logging.getLogger(__name__)

def log_proxy_configuration():
    """Log current proxy configuration for monitoring."""
    injector = get_proxy_injector()
    if not injector:
        logger.info("Direct connections (no proxy)")
        return
    
    exchanges = ['binance', 'coinbase', 'backpack']
    for exchange in exchanges:
        http_url = injector.get_http_proxy_url(exchange)
        logger.info(f"{exchange}: HTTP proxy={http_url or 'direct'}")

# Log at application startup
log_proxy_configuration()
```

This user guide provides comprehensive coverage of proxy system usage without overwhelming technical implementation details. For deeper technical information, see the [Technical Specification](technical-specification.md).
