# Proxy System External Delegation - Implementation Update

## Overview
This document outlines the specific code changes required to extend the current proxy system with external service delegation capabilities while maintaining 100% backward compatibility.

## Key Implementation Changes

### 1. Enhanced Configuration Models

#### New External Service Configuration
```python
class ExternalProxyServiceConfig(BaseModel):
    """Configuration for external proxy service integration."""
    model_config = ConfigDict(extra='forbid')
    
    enabled: bool = Field(default=False, description="Enable external proxy service")
    endpoints: List[str] = Field(default_factory=list, description="Proxy service endpoints")
    auth_method: Literal['bearer_token', 'api_key', 'mutual_tls'] = Field(
        default='bearer_token', 
        description="Authentication method"
    )
    auth_credentials: Dict[str, str] = Field(
        default_factory=dict, 
        description="Authentication credentials"
    )
    timeout_seconds: int = Field(
        default=10, ge=1, le=60, 
        description="Request timeout"
    )
    cache_ttl_seconds: int = Field(
        default=300, ge=60, le=3600, 
        description="Default cache TTL"
    )
    circuit_breaker_enabled: bool = Field(
        default=True, 
        description="Enable circuit breaker"
    )
    fallback_to_embedded: bool = Field(
        default=True, 
        description="Fall back to embedded config"
    )
```

#### Extended ProxySettings Class
```python
class ProxySettings(BaseSettings):
    """Enhanced proxy settings with external service support."""
    model_config = ConfigDict(
        env_prefix='CRYPTOFEED_PROXY_',
        env_nested_delimiter='__',
        case_sensitive=False,
        extra='forbid'
    )
    
    # Existing fields (unchanged for backward compatibility)
    enabled: bool = Field(default=False, description="Enable proxy functionality")
    default: Optional[ConnectionProxies] = Field(
        default=None, 
        description="Default proxy configuration for all exchanges"
    )
    exchanges: Dict[str, ConnectionProxies] = Field(
        default_factory=dict,
        description="Exchange-specific proxy overrides"
    )
    
    # New external service configuration
    external_service: ExternalProxyServiceConfig = Field(
        default_factory=ExternalProxyServiceConfig,
        description="External proxy service configuration"
    )
    
    # Existing method (unchanged)
    def get_proxy(self, exchange_id: str, connection_type: Literal['http', 'websocket']) -> Optional[ProxyConfig]:
        """Get proxy configuration for specific exchange and connection type."""
        # Implementation unchanged - maintains backward compatibility
        if not self.enabled:
            return None
        
        if exchange_id in self.exchanges:
            proxy = getattr(self.exchanges[exchange_id], connection_type, None)
            if proxy is not None:
                return proxy
        
        if self.default:
            return getattr(self.default, connection_type, None)
        
        return None
```

### 2. External Service Client Implementation

#### Service Request/Response Models
```python
class ProxyRequest(BaseModel):
    """Request for proxy from external service."""
    model_config = ConfigDict(extra='forbid')
    
    exchange_id: str = Field(..., description="Exchange identifier")
    connection_type: Literal['http', 'websocket'] = Field(..., description="Connection type")
    region: Optional[str] = Field(default=None, description="Preferred region")
    client_id: str = Field(..., description="Client instance identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

class ProxyResponse(BaseModel):
    """Response from external proxy service."""
    model_config = ConfigDict(extra='forbid')
    
    proxy_url: str = Field(..., description="Proxy URL to use")
    strategy: str = Field(..., description="Selection strategy used")
    ttl_seconds: int = Field(..., ge=60, description="Cache TTL")
    fallback_policy: Literal['direct_connection', 'embedded_fallback', 'fail'] = Field(
        default='embedded_fallback',
        description="Fallback policy when proxy fails"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")

class ProxyFeedback(BaseModel):
    """Feedback about proxy usage."""
    model_config = ConfigDict(extra='forbid')
    
    proxy_url: str = Field(..., description="Proxy URL that was used")
    exchange_id: str = Field(..., description="Exchange identifier")
    connection_type: Literal['http', 'websocket'] = Field(..., description="Connection type")
    success: bool = Field(..., description="Whether connection succeeded")
    latency_ms: Optional[int] = Field(default=None, description="Connection latency")
    error_details: Optional[str] = Field(default=None, description="Error details if failed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp")
    client_id: str = Field(..., description="Client instance identifier")
```

#### Proxy Service Client
```python
class ProxyServiceClient:
    """Client for communicating with external proxy services."""
    
    def __init__(self, config: ExternalProxyServiceConfig):
        self.config = config
        self.circuit_breaker = CircuitBreaker() if config.circuit_breaker_enabled else None
        self.cache = ProxyResponseCache(default_ttl=config.cache_ttl_seconds)
        self.client_id = f"cryptofeed-{socket.gethostname()}-{os.getpid()}"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_proxy(self, request: ProxyRequest) -> Optional[ProxyResponse]:
        """Request proxy from external service with caching and circuit breaker."""
        # Check cache first
        cache_key = self._generate_cache_key(request)
        cached_response = self.cache.get(cache_key)
        if cached_response:
            LOG.debug(f"Cache hit for proxy request: {cache_key}")
            return cached_response
        
        # Circuit breaker protection
        if self.circuit_breaker and self.circuit_breaker.is_open():
            LOG.warning("Circuit breaker is open, skipping external service")
            return None
        
        try:
            response = await self._make_service_request(request)
            if response:
                self.cache.put(cache_key, response)
                if self.circuit_breaker:
                    self.circuit_breaker.record_success()
            return response
            
        except Exception as e:
            LOG.error(f"Proxy service request failed: {e}")
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            return None
    
    async def report_feedback(self, feedback: ProxyFeedback) -> None:
        """Report proxy usage feedback (fire-and-forget)."""
        try:
            await self._make_feedback_request(feedback)
        except Exception as e:
            LOG.warning(f"Failed to report proxy feedback: {e}")
            # Don't raise - feedback is non-critical
    
    async def _make_service_request(self, request: ProxyRequest) -> Optional[ProxyResponse]:
        """Make HTTP request to proxy service."""
        if not self.session:
            raise RuntimeError("ProxyServiceClient not initialized")
        
        headers = self._get_auth_headers()
        request.client_id = self.client_id
        
        for endpoint in self.config.endpoints:
            try:
                url = f"{endpoint}/api/v1/proxy/request"
                async with self.session.post(url, json=request.dict(), headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return ProxyResponse(**data)
                    else:
                        LOG.warning(f"Proxy service returned {resp.status}: {await resp.text()}")
            except Exception as e:
                LOG.warning(f"Failed to contact proxy service {endpoint}: {e}")
                continue
        
        return None
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers based on configured method."""
        if self.config.auth_method == 'bearer_token':
            token = self.config.auth_credentials.get('token')
            return {'Authorization': f'Bearer {token}'} if token else {}
        elif self.config.auth_method == 'api_key':
            api_key = self.config.auth_credentials.get('api_key')
            return {'X-API-Key': api_key} if api_key else {}
        return {}
```

### 3. Enhanced ProxyInjector with Service Delegation

```python
class ProxyInjector:
    """Enhanced proxy injector with external service delegation."""
    
    def __init__(self, proxy_settings: ProxySettings, service_client: Optional[ProxyServiceClient] = None):
        self.settings = proxy_settings
        self.service_client = service_client
        self.external_enabled = (
            service_client is not None and 
            proxy_settings.external_service.enabled
        )
    
    async def get_http_proxy_url(self, exchange_id: str) -> Optional[str]:
        """Get HTTP proxy URL with external service delegation."""
        # Try external service first if enabled
        if self.external_enabled:
            proxy_url = await self._get_proxy_from_service(exchange_id, 'http')
            if proxy_url:
                return proxy_url
            
            # Log fallback usage
            if self.settings.external_service.fallback_to_embedded:
                LOG.info(f"Falling back to embedded proxy config for {exchange_id}")
            else:
                LOG.warning(f"External service failed and fallback disabled for {exchange_id}")
                return None
        
        # Fallback to embedded configuration
        proxy_config = self.settings.get_proxy(exchange_id, 'http')
        return proxy_config.url if proxy_config else None
    
    async def create_websocket_connection(self, url: str, exchange_id: str, **kwargs):
        """Create WebSocket connection with external service delegation."""
        proxy_url = None
        
        # Try external service first if enabled
        if self.external_enabled:
            proxy_url = await self._get_proxy_from_service(exchange_id, 'websocket')
        
        # Fallback to embedded configuration if no external proxy
        if not proxy_url:
            proxy_config = self.settings.get_proxy(exchange_id, 'websocket')
            proxy_url = proxy_config.url if proxy_config else None
        
        # Proceed with connection logic (unchanged from current implementation)
        if not proxy_url:
            return await websockets.connect(url, **kwargs)
        
        # Apply proxy configuration and create connection
        connect_kwargs = dict(kwargs)
        parsed = urlparse(proxy_url)
        scheme = parsed.scheme
        
        log_proxy_usage(transport='websocket', exchange_id=exchange_id, proxy_url=proxy_url)
        
        start_time = datetime.now(UTC)
        try:
            if scheme in ('socks4', 'socks5'):
                try:
                    __import__('python_socks')
                except ModuleNotFoundError as exc:
                    raise ImportError("python-socks library required for SOCKS proxy support") from exc
            elif scheme in ('http', 'https'):
                header_key = 'extra_headers' if 'extra_headers' in connect_kwargs else 'additional_headers'
                existing_headers = connect_kwargs.get(header_key, {})
                headers = dict(existing_headers) if existing_headers else {}
                headers.setdefault('Proxy-Connection', 'keep-alive')
                connect_kwargs[header_key] = headers
            
            connect_kwargs['proxy'] = proxy_url
            connection = await websockets.connect(url, **connect_kwargs)
            
            # Report success feedback if using external service
            if self.external_enabled and self.service_client:
                latency_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                feedback = ProxyFeedback(
                    proxy_url=proxy_url,
                    exchange_id=exchange_id,
                    connection_type='websocket',
                    success=True,
                    latency_ms=latency_ms,
                    client_id=self.service_client.client_id
                )
                asyncio.create_task(self.service_client.report_feedback(feedback))
            
            return connection
            
        except Exception as e:
            # Report failure feedback if using external service
            if self.external_enabled and self.service_client:
                feedback = ProxyFeedback(
                    proxy_url=proxy_url,
                    exchange_id=exchange_id,
                    connection_type='websocket',
                    success=False,
                    error_details=str(e),
                    client_id=self.service_client.client_id
                )
                asyncio.create_task(self.service_client.report_feedback(feedback))
            
            raise
    
    async def _get_proxy_from_service(self, exchange_id: str, connection_type: str) -> Optional[str]:
        """Get proxy URL from external service."""
        if not self.service_client:
            return None
        
        request = ProxyRequest(
            exchange_id=exchange_id,
            connection_type=connection_type,
            client_id=self.service_client.client_id
        )
        
        response = await self.service_client.get_proxy(request)
        return response.proxy_url if response else None
```

### 4. Initialization Integration

```python
# Enhanced initialization with external service support
async def init_proxy_system_async(settings: ProxySettings) -> None:
    """Initialize proxy system with optional external service integration."""
    global _proxy_injector
    
    if not settings.enabled:
        _proxy_injector = None
        return
    
    service_client = None
    if settings.external_service.enabled:
        service_client = ProxyServiceClient(settings.external_service)
        # Note: Service client uses async context manager, so it would be managed
        # by the application lifecycle (e.g., in feedhandler startup/shutdown)
    
    _proxy_injector = ProxyInjector(settings, service_client)

# Backward compatible synchronous initialization (unchanged)
def init_proxy_system(settings: ProxySettings) -> None:
    """Initialize proxy system (synchronous, no external service)."""
    global _proxy_injector
    if settings.enabled:
        _proxy_injector = ProxyInjector(settings)
    else:
        _proxy_injector = None
```

## Environment Configuration Examples

### External Service Configuration
```bash
# Enable external proxy service
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__ENABLED=true
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__ENDPOINTS=["https://proxy-service-1:8080", "https://proxy-service-2:8080"]
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__AUTH_METHOD=bearer_token
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__AUTH_CREDENTIALS__TOKEN=your-service-token
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__TIMEOUT_SECONDS=10
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__CACHE_TTL_SECONDS=300
CRYPTOFEED_PROXY_EXTERNAL_SERVICE__FALLBACK_TO_EMBEDDED=true

# Embedded fallback configuration (preserved)
CRYPTOFEED_PROXY_ENABLED=true
CRYPTOFEED_PROXY_DEFAULT__HTTP__URL=socks5://fallback-proxy:1080
CRYPTOFEED_PROXY_DEFAULT__WEBSOCKET__URL=socks5://fallback-proxy:1080
```

### YAML Configuration
```yaml
proxy:
  enabled: true
  
  # External service configuration
  external_service:
    enabled: true
    endpoints:
      - "https://proxy-service-1:8080"
      - "https://proxy-service-2:8080"
    auth_method: "bearer_token"
    auth_credentials:
      token: "your-service-token"
    timeout_seconds: 10
    cache_ttl_seconds: 300
    fallback_to_embedded: true
  
  # Embedded fallback configuration
  default:
    http:
      url: "socks5://fallback-proxy:1080"
    websocket:
      url: "socks5://fallback-proxy:1080"
```

## Migration Path and Compatibility

### Phase 1: No Changes Required
- Existing configurations continue working unchanged
- External service features disabled by default
- Zero impact on current deployments

### Phase 2: Optional External Service
- Enable external service with fallback to embedded
- Gradual testing and validation
- Full backward compatibility maintained

### Phase 3: Primary External Service
- External service as primary with embedded backup
- Enhanced monitoring and analytics
- Optional removal of embedded pools for pure external service deployments

## Testing Strategy

### Backward Compatibility Tests
```python
def test_existing_configurations_unchanged():
    """Verify all existing proxy configurations continue working."""
    # Test existing environment variable configurations
    # Test existing YAML configurations  
    # Test existing programmatic configurations
    # Verify no behavioral changes in proxy resolution

def test_external_service_disabled_by_default():
    """Verify external service is disabled by default."""
    settings = ProxySettings()
    assert not settings.external_service.enabled
    
    injector = ProxyInjector(settings)
    assert not injector.external_enabled
```

### External Service Integration Tests
```python
@pytest.mark.asyncio
async def test_external_service_with_fallback():
    """Test external service with embedded fallback."""
    # Mock external service unavailable
    # Verify fallback to embedded configuration
    # Confirm no connection failures

@pytest.mark.asyncio  
async def test_proxy_feedback_reporting():
    """Test feedback reporting for external service."""
    # Mock successful connection
    # Verify feedback is reported
    # Test failure scenarios
```

This implementation update maintains 100% backward compatibility while adding comprehensive external service delegation capabilities with robust fallback mechanisms.