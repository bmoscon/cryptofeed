# Transparent Proxy Configuration Patterns

## Quick Start: Zero Code Changes Required

**The key principle**: Your existing exchange configuration remains unchanged. Proxy settings are added separately and applied transparently.

```yaml
# Your existing exchange config - NO CHANGES NEEDED
exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
  
  coinbase:
    symbols: ["BTC-USD"]
    channels: [TRADES]

# NEW: Add proxy configuration - existing code continues to work
proxy:
  enabled: true
  default:
    rest: socks5://your-proxy:1080
    websocket: socks5://your-proxy:1081
```

**Result**: All exchanges automatically use the configured proxy with zero code changes.

## Common Configuration Patterns

### 1. Simple Global Proxy

**Use Case**: Route all exchange traffic through a single proxy server.

```yaml
proxy:
  enabled: true
  auto_inject: true
  
  # All exchanges use this proxy
  default:
    rest: socks5://company-proxy.internal:1080
    websocket: socks5://company-proxy.internal:1081
    timeout: 30

# Your existing exchanges - unchanged
exchanges:
  binance:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
    
  kraken:
    symbols: ["ETH-USD"]
    channels: [L2_BOOK]
```

### 2. Exchange-Specific Proxies

**Use Case**: Different proxies for different exchanges (e.g., regional compliance).

```yaml
proxy:
  enabled: true
  
  # Default for most exchanges
  default:
    rest: socks5://global-proxy:1080
    websocket: socks5://global-proxy:1081
  
  # Exchange-specific overrides
  exchanges:
    binance:
      # Binance-specific proxy for compliance
      rest: http://binance-proxy.compliance.company.com:8080
      websocket: socks5://binance-ws.compliance.company.com:1081
    
    huobi:
      # Huobi-specific proxy
      rest: socks5://huobi-proxy:1080
      # websocket will use default
    
    coinbase:
      # No proxy for Coinbase (uses direct connection)
      rest: null
      websocket: null

exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    
  huobi:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
    
  coinbase:
    symbols: ["BTC-USD"]
    channels: [TRADES]
```

### 3. Regional Auto-Detection

**Use Case**: Automatically apply proxies based on detected region/location.

```yaml
proxy:
  enabled: true
  
  # Regional auto-detection
  regional:
    enabled: true
    detection_method: "geoip"
    
    rules:
      # US/Canada: Use compliance proxies for restricted exchanges
      - regions: ["US", "CA"]
        exchanges: ["binance", "huobi", "okx"]
        proxy: "socks5://us-compliance.company.com:1080"
        
      # China: Use VPN proxy for all exchanges
      - regions: ["CN"]
        exchanges: ["*"]  # All exchanges
        proxy: "socks5://china-vpn.company.com:1080"
        
      # EU: Special Binance proxy for GDPR compliance
      - regions: ["EU", "GB"]
        exchanges: ["binance"]
        proxy: "http://eu-binance.compliance.company.com:8080"
    
    # Fallback if no region-specific rule matches
    fallback_proxy: "socks5://global-fallback.company.com:1080"

# Your exchanges - no changes needed
exchanges:
  binance:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
    
  huobi:
    symbols: ["ETH-USDT"]
    channels: [L2_BOOK]
```

### 4. External Proxy Manager Integration

**Use Case**: Enterprise environments with dynamic proxy management.

```yaml
proxy:
  enabled: true
  
  # External proxy manager (e.g., Kubernetes, HashiCorp Vault)
  manager:
    enabled: true
    plugin: "company.proxy.K8sProxyManager"
    
    config:
      # Kubernetes configuration
      namespace: "trading-infrastructure"
      service_name: "proxy-service"
      refresh_interval: 300  # 5 minutes
      
      # Service discovery
      discovery:
        method: "dns"
        pattern: "proxy-{exchange}.trading.svc.cluster.local"
      
      # Authentication
      auth:
        method: "service_account"
        account: "cryptofeed-sa"
    
    # Fallback to static config if manager fails
    fallback_to_static: true
    
  # Static fallback configuration
  default:
    rest: socks5://fallback-proxy.company.com:1080
    websocket: socks5://fallback-proxy.company.com:1081

exchanges:
  binance:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
```

### 5. Development vs Production Patterns

**Development Environment**:
```yaml
# dev-config.yaml
proxy:
  enabled: false  # No proxy in development
  
  # Optional: Development proxy for testing
  development:
    enabled: true
    default:
      rest: http://localhost:8888  # Local proxy for testing
      websocket: socks5://localhost:1080

exchanges:
  binance_testnet:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
```

**Production Environment**:
```yaml
# prod-config.yaml
proxy:
  enabled: true
  auto_inject: true
  
  # Production proxy configuration
  default:
    rest: socks5://prod-proxy-lb.company.com:1080
    websocket: socks5://prod-proxy-lb.company.com:1081
  
  # High availability configuration
  manager:
    enabled: true
    plugin: "company.proxy.HAProxyManager"
    config:
      primary_proxy: "socks5://proxy-1.company.com:1080"
      backup_proxies:
        - "socks5://proxy-2.company.com:1080"
        - "socks5://proxy-3.company.com:1080"
      health_check_interval: 30
      failover_timeout: 10
  
  # Monitoring and logging
  logging:
    level: "INFO"
    log_proxy_usage: true
    log_credentials: false
    
  health_check:
    enabled: true
    interval: 60
    timeout: 5

exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT", "BNB-USDT"]
    channels: [TRADES, L2_BOOK, TICKER]
```

## Advanced Configuration Scenarios

### 1. Multi-Region Trading Infrastructure

**Use Case**: Global trading firm with region-specific proxy requirements.

```yaml
proxy:
  enabled: true
  
  # Region-specific proxy pools
  regions:
    us_east:
      exchanges: ["coinbase", "kraken"]
      proxies:
        rest: "socks5://us-east-proxy-pool.company.com:1080"
        websocket: "socks5://us-east-proxy-pool.company.com:1081"
      
    us_west:
      exchanges: ["binance"]  # Binance US
      proxies:
        rest: "http://us-west-binance.company.com:8080"
        websocket: "socks5://us-west-binance.company.com:1081"
    
    europe:
      exchanges: ["binance", "bitstamp"]
      proxies:
        rest: "socks5://eu-proxy-pool.company.com:1080"
        websocket: "socks5://eu-proxy-pool.company.com:1081"
    
    asia:
      exchanges: ["huobi", "okx"]
      proxies:
        rest: "socks5://asia-proxy-pool.company.com:1080"
        websocket: "socks5://asia-proxy-pool.company.com:1081"
  
  # Load balancing across regions
  load_balancing:
    enabled: true
    method: "round_robin"  # or "least_connections", "random"
    health_check: true

exchanges:
  # US exchanges
  coinbase:
    symbols: ["BTC-USD", "ETH-USD"]
    channels: [TRADES, L2_BOOK]
    
  # European exchanges  
  bitstamp:
    symbols: ["BTC-EUR", "ETH-EUR"]
    channels: [TRADES]
    
  # Asian exchanges
  huobi:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
```

### 2. Compliance and Security Patterns

**Use Case**: Financial institution with strict compliance requirements.

```yaml
proxy:
  enabled: true
  
  # Compliance rules
  compliance:
    enabled: true
    
    # Data residency requirements
    data_residency:
      - region: "EU"
        exchanges: ["*"]
        requirement: "gdpr_compliant_proxy"
        proxy: "socks5://eu-gdpr-proxy.compliance.company.com:1080"
      
      - region: "US"
        exchanges: ["binance", "huobi"]
        requirement: "us_restricted_proxy"
        proxy: "http://us-compliance.company.com:8080"
    
    # Audit logging
    audit:
      enabled: true
      log_all_connections: true
      retention_days: 2555  # 7 years
      encryption: "AES-256"
      
    # Security controls
    security:
      # Only allow specific proxy servers
      allowed_proxies:
        - "*.compliance.company.com"
        - "approved-proxy.vendor.com"
      
      # Require authentication for all proxies
      require_authentication: true
      
      # Certificate validation
      verify_certificates: true
      certificate_store: "/etc/ssl/company-certs"
      
      # Network policies
      firewall_rules:
        - "allow proxy traffic on ports 1080-1090"
        - "block direct exchange connections"

# Security-focused exchange configuration
exchanges:
  binance:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
    # Compliance: Will automatically use approved proxy
    
  coinbase:
    symbols: ["BTC-USD"]
    channels: [TRADES]
    # Compliance: Direct connection allowed for US-based exchange
```

### 3. High-Performance Trading Setup

**Use Case**: Low-latency trading with optimized proxy configuration.

```yaml
proxy:
  enabled: true
  
  # Performance optimization
  performance:
    # Connection pooling for reduced latency
    connection_pooling:
      enabled: true
      pool_size: 10
      max_connections_per_host: 5
      keep_alive_timeout: 30
    
    # Proxy selection based on latency
    latency_optimization:
      enabled: true
      preferred_latency_ms: 50
      fallback_latency_ms: 200
      
    # Bypass proxy for low-latency exchanges
    latency_bypass:
      enabled: true
      threshold_ms: 10
      exchanges: ["coinbase"]  # Direct connection for lowest latency
  
  # High-performance proxy pool
  high_performance:
    exchanges: ["binance", "kraken"]
    proxies:
      # Multiple proxies for load distribution
      rest:
        - "socks5://hp-proxy-1.company.com:1080"
        - "socks5://hp-proxy-2.company.com:1080"
        - "socks5://hp-proxy-3.company.com:1080"
      websocket:
        - "socks5://hp-ws-1.company.com:1081"
        - "socks5://hp-ws-2.company.com:1081"
    
    # Load balancing for optimal performance
    load_balancing:
      method: "least_latency"
      health_check_interval: 10
      connection_timeout: 5
  
  # Monitoring for performance optimization
  monitoring:
    latency_tracking: true
    throughput_monitoring: true
    connection_success_rate: true
    alert_thresholds:
      latency_ms: 100
      success_rate_percent: 95

exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    
  coinbase:
    symbols: ["BTC-USD"]
    channels: [TRADES]
    # Will use direct connection for lowest latency
```

## Integration Examples

### 1. Docker Compose with Proxy

```yaml
# docker-compose.yml
version: '3.8'

services:
  cryptofeed:
    image: cryptofeed:latest
    volumes:
      - ./config.yaml:/app/config.yaml
    environment:
      - CRYPTOFEED_CONFIG=/app/config.yaml
    depends_on:
      - proxy-service
    
  proxy-service:
    image: company/trading-proxy:latest
    ports:
      - "1080:1080"  # SOCKS5
      - "8080:8080"  # HTTP
    environment:
      - PROXY_MODE=socks5
      - UPSTREAM_SERVERS=proxy-1.company.com,proxy-2.company.com
```

```yaml
# config.yaml
proxy:
  enabled: true
  default:
    rest: socks5://proxy-service:1080
    websocket: socks5://proxy-service:1080

exchanges:
  binance:
    symbols: ["BTC-USDT"]
    channels: [TRADES]
```

### 2. Kubernetes Deployment

```yaml
# cryptofeed-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cryptofeed
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cryptofeed
  template:
    metadata:
      labels:
        app: cryptofeed
    spec:
      serviceAccountName: cryptofeed-sa
      containers:
      - name: cryptofeed
        image: cryptofeed:latest
        env:
        - name: CRYPTOFEED_CONFIG
          value: /config/config.yaml
        volumeMounts:
        - name: config-volume
          mountPath: /config
      volumes:
      - name: config-volume
        configMap:
          name: cryptofeed-config

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: cryptofeed-config
data:
  config.yaml: |
    proxy:
      enabled: true
      manager:
        enabled: true
        plugin: "k8s_proxy_manager.K8sProxyManager"
        config:
          namespace: "trading-infrastructure"
          service_name: "proxy-service"
    
    exchanges:
      binance:
        symbols: ["BTC-USDT"]
        channels: [TRADES]
```

### 3. Environment-Based Configuration

```bash
# Environment variables for proxy configuration
export CRYPTOFEED_PROXY_ENABLED=true
export CRYPTOFEED_PROXY_DEFAULT_REST="socks5://proxy:1080"
export CRYPTOFEED_PROXY_DEFAULT_WEBSOCKET="socks5://proxy:1081"

# Exchange-specific overrides
export CRYPTOFEED_PROXY_BINANCE_REST="http://binance-proxy:8080"
export CRYPTOFEED_PROXY_BINANCE_WEBSOCKET="socks5://binance-ws:1081"

# Run cryptofeed - will automatically use environment proxy configuration
python -m cryptofeed config.yaml
```

## Migration Guide: Adding Proxies to Existing Setup

### Step 1: Current Setup (No Changes Needed)

```yaml
# Your existing config.yaml - KEEP AS-IS
exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    
  coinbase:
    symbols: ["BTC-USD", "ETH-USD"]
    channels: [TRADES]
```

### Step 2: Add Proxy Configuration

```yaml
# Add this section to your existing config.yaml
proxy:
  enabled: true
  default:
    rest: socks5://your-proxy-server:1080
    websocket: socks5://your-proxy-server:1081

# Your existing exchanges section - NO CHANGES NEEDED
exchanges:
  binance:
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    
  coinbase:
    symbols: ["BTC-USD", "ETH-USD"]
    channels: [TRADES]
```

### Step 3: Test and Verify

```python
# Your existing Python code - NO CHANGES NEEDED
from cryptofeed import FeedHandler

config = load_config('config.yaml')
fh = FeedHandler(config=config)
fh.run()

# Proxies are now automatically applied!
```

**Result**: Your existing code works identically, now with transparent proxy support.

## Troubleshooting Common Patterns

### 1. Proxy Connection Issues

```yaml
proxy:
  enabled: true
  
  # Enhanced debugging
  logging:
    level: "DEBUG"
    log_proxy_usage: true
    log_connection_attempts: true
    
  # Health checking
  health_check:
    enabled: true
    interval: 30
    timeout: 10
    test_endpoints:
      rest: "https://httpbin.org/ip"
      websocket: "wss://echo.websocket.org"
  
  # Fallback behavior
  fallback:
    enabled: true
    method: "direct_connection"  # or "backup_proxy"
    backup_proxy: "socks5://backup-proxy:1080"
    
  default:
    rest: socks5://primary-proxy:1080
    websocket: socks5://primary-proxy:1081
```

### 2. Performance Monitoring

```yaml
proxy:
  enabled: true
  
  # Performance monitoring
  monitoring:
    enabled: true
    
    # Latency tracking
    latency:
      track_connection_time: true
      track_request_time: true
      alert_threshold_ms: 1000
      
    # Throughput monitoring
    throughput:
      track_bytes_sent: true
      track_bytes_received: true
      track_requests_per_second: true
      
    # Success rate monitoring
    success_rate:
      track_connection_success: true
      track_request_success: true
      alert_threshold_percent: 95
      
    # Export metrics
    metrics:
      prometheus_enabled: true
      prometheus_port: 9090
      grafana_dashboard: true
```

**Summary**: The transparent proxy injection system provides enterprise-grade proxy support with zero code changes required. Existing exchanges and user code continue to work identically, while gaining powerful proxy capabilities through configuration alone.