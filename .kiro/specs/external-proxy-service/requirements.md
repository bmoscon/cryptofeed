# External Proxy Service Delegation Requirements

## Project Description
Transform cryptofeed's embedded proxy management into a service-oriented architecture where proxy inventory, health checking, load balancing, and rotation are delegated to external specialized proxy services, reducing client complexity and enabling centralized proxy operations.

## Engineering Principles Applied
- **SEPARATION OF CONCERNS**: Delegate proxy management to specialized services
- **LOOSE COUPLING**: Cryptofeed clients request proxies via API, don't manage pools
- **CIRCUIT BREAKER**: Graceful degradation when proxy service unavailable
- **OBSERVABLE**: Centralized metrics and monitoring for proxy operations
- **STATELESS**: Clients don't maintain proxy state, service provides all intelligence

## Requirements

### Functional Requirements (Service Delegation)
1. **FR-1**: External Proxy Service Integration
   - WHEN cryptofeed needs proxy THEN client SHALL request proxy from external service API
   - WHEN service provides proxy THEN client SHALL use proxy for connection establishment
   - WHEN proxy connection fails THEN client SHALL report failure to service for health tracking
   - WHEN service unavailable THEN client SHALL fall back to embedded proxy configuration

2. **FR-2**: Proxy Request and Response Protocol
   - WHEN requesting proxy THEN client SHALL specify exchange_id, connection_type, region
   - WHEN service responds THEN response SHALL include proxy_url, selection_metadata, ttl
   - WHEN proxy has authentication THEN service SHALL provide complete proxy URL with credentials
   - WHEN no proxy available THEN service SHALL return fallback directive or direct connection

3. **FR-3**: Proxy Usage Feedback and Health Reporting
   - WHEN connection succeeds THEN client SHALL report success with latency metrics
   - WHEN connection fails THEN client SHALL report failure with error details
   - WHEN proxy becomes unresponsive THEN client SHALL report timeout for immediate health update
   - WHEN connection established THEN client SHALL report connection start for load tracking

4. **FR-4**: Service Discovery and Resilience
   - WHEN proxy service endpoint changes THEN client SHALL discover new endpoint automatically
   - WHEN proxy service fails THEN client SHALL retry with exponential backoff
   - WHEN all proxy services unavailable THEN client SHALL use embedded fallback configuration
   - WHEN service recovers THEN client SHALL resume delegated proxy requests

### Technical Requirements (Client Implementation)
1. **TR-1**: Proxy Service Client Architecture
   - Replace embedded ProxyPool with ProxyServiceClient
   - Maintain ProxyInjector interface for backward compatibility
   - Implement async HTTP client for proxy service communication
   - Add circuit breaker pattern for service reliability

2. **TR-2**: Request/Response Data Models
   - Define ProxyRequest model (exchange_id, connection_type, region, metadata)
   - Define ProxyResponse model (proxy_url, strategy_info, ttl, fallback_policy)
   - Define ProxyFeedback model (proxy_url, success, latency, error_details, timestamp)
   - Maintain type safety with Pydantic v2 validation

3. **TR-3**: Caching and Performance Optimization
   - Cache proxy responses based on TTL to reduce service calls
   - Implement connection pooling for proxy service HTTP client
   - Use request compression for high-volume feedback reporting
   - Batch feedback reports for improved efficiency

4. **TR-4**: Configuration and Service Discovery
   - Configure proxy service endpoints via environment variables
   - Support multiple proxy service instances for high availability
   - Implement health checking for proxy service endpoints
   - Fall back to embedded configuration when services unavailable

### Non-Functional Requirements (Quality Attributes)
1. **NFR-1**: Performance and Latency
   - Proxy resolution latency < 10ms for cached responses
   - Service unavailability detected within 2 seconds
   - Fallback to embedded configuration within 1 second of service failure
   - Feedback reporting does not block connection establishment

2. **NFR-2**: Reliability and Availability
   - Client continues operating with 99.9% reliability when service unavailable
   - Graceful degradation with no connection failures during service outages
   - Automatic recovery when proxy services become available
   - No proxy service dependency for direct connection fallback

3. **NFR-3**: Observability and Monitoring
   - All proxy requests/responses logged with correlation IDs
   - Service communication metrics integrated with existing cryptofeed monitoring
   - Clear error messages for service communication failures
   - Health status of proxy service endpoints visible in application logs

4. **NFR-4**: Security and Authentication
   - Proxy service communication over HTTPS with certificate validation
   - API authentication via Bearer tokens or mutual TLS
   - Proxy credentials encrypted in transit and at rest
   - No sensitive proxy information logged in clear text

## External Proxy Service Interface Specification

### Proxy Request Endpoint
```http
POST /api/v1/proxy/request
Content-Type: application/json
Authorization: Bearer <token>

{
  "exchange_id": "binance",
  "connection_type": "websocket",
  "region": "us-east-1",
  "client_id": "cryptofeed-instance-123",
  "metadata": {
    "feed_types": ["trades", "book"],
    "symbols": ["BTC-USD", "ETH-USD"]
  }
}
```

### Proxy Response Format
```http
200 OK
Content-Type: application/json

{
  "proxy_url": "socks5://user:pass@proxy-server:1080",
  "strategy": "least_connections",
  "ttl_seconds": 300,
  "fallback_policy": "direct_connection",
  "metadata": {
    "proxy_id": "proxy-123",
    "region": "us-east-1",
    "health_score": 0.98
  }
}
```

### Feedback Reporting Endpoint
```http
POST /api/v1/proxy/feedback
Content-Type: application/json
Authorization: Bearer <token>

{
  "proxy_url": "socks5://user:pass@proxy-server:1080",
  "exchange_id": "binance",
  "connection_type": "websocket",
  "success": true,
  "latency_ms": 45,
  "error_details": null,
  "timestamp": "2024-09-23T10:30:00Z",
  "client_id": "cryptofeed-instance-123"
}
```

## Backward Compatibility Strategy

### Embedded Fallback Configuration
- Maintain existing ProxySettings for fallback when service unavailable
- Preserve all existing proxy configuration methods (environment, YAML, programmatic)
- Embed minimal proxy pool as last resort for critical operations
- Enable/disable external service delegation via configuration flag

### Migration Path
1. **Phase 1**: Add external service client alongside existing proxy system
2. **Phase 2**: Route requests through service with embedded fallback
3. **Phase 3**: Deprecate embedded pools while maintaining configuration compatibility
4. **Phase 4**: Optional removal of embedded proxy management (configuration only)

## Success Metrics
- **Service Integration**: Successful proxy requests via external service
- **Reliability**: Zero connection failures during service unavailability
- **Performance**: < 10ms proxy resolution latency for cached responses
- **Observability**: Complete audit trail of proxy service interactions
- **Backward Compatibility**: All existing proxy configurations continue working

## Implementation Priority
1. **HIGH**: Proxy service client and request/response protocol
2. **HIGH**: Circuit breaker and fallback to embedded configuration
3. **MEDIUM**: Caching and performance optimization
4. **MEDIUM**: Comprehensive feedback reporting and metrics
5. **LOW**: Advanced features (compression, batching, service discovery)