"""
Simple Proxy System MVP - START SMALL Implementation

Following engineering principles from CLAUDE.md:
- START SMALL: MVP functionality only
- FRs over NFRs: Core proxy support, deferred enterprise features  
- Pydantic v2: Type-safe configuration with validation
- YAGNI: No external managers, HA, monitoring until proven needed
- KISS: Simple ProxyInjector instead of complex resolver hierarchy
"""
from __future__ import annotations

import aiohttp
import websockets
import logging
import asyncio
import socket
import random
from abc import ABC, abstractmethod
from datetime import datetime, UTC
from typing import Optional, Literal, Dict, Any, Tuple, List, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


LOG = logging.getLogger('feedhandler')


class ProxyUrlConfig(BaseModel):
    """Individual proxy URL configuration within pools."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    
    url: str = Field(..., description="Proxy URL (e.g., socks5://user:pass@host:1080)")
    weight: float = Field(default=1.0, ge=0.1, le=10.0, description="Proxy weight for selection")
    enabled: bool = Field(default=True, description="Whether proxy is enabled")
    
    @field_validator('url')
    @classmethod
    def validate_proxy_url(cls, v: str) -> str:
        """Validate proxy URL format and scheme."""
        parsed = urlparse(v)
        
        # Check for valid URL format - should have '://' for scheme
        if '://' not in v:
            raise ValueError("Proxy URL must include scheme")
            
        if not parsed.scheme:
            raise ValueError("Proxy URL must include scheme")
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


class ProxyPoolConfig(BaseModel):
    """Proxy pool configuration with multiple proxies and selection strategy."""
    model_config = ConfigDict(extra='forbid')
    
    proxies: List[ProxyUrlConfig] = Field(..., min_length=1, description="List of proxy configurations")
    strategy: Literal['round_robin', 'random', 'least_connections'] = Field(
        default='round_robin', 
        description="Proxy selection strategy"
    )


class ProxyConfig(BaseModel):
    """Single proxy configuration with URL validation, extended to support pools."""
    model_config = ConfigDict(frozen=True, extra='forbid')
    
    # Single proxy configuration (existing)
    url: Optional[str] = Field(default=None, description="Proxy URL (e.g., socks5://user:pass@host:1080)")
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    
    # Pool configuration (new)
    pool: Optional[ProxyPoolConfig] = Field(default=None, description="Proxy pool configuration")
    
    @field_validator('url')
    @classmethod
    def validate_proxy_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate proxy URL format and scheme."""
        if v is None:
            return v
            
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
    def scheme(self) -> Optional[str]:
        """Extract proxy scheme."""
        if self.url:
            return urlparse(self.url).scheme
        return None
    
    @property
    def host(self) -> Optional[str]:
        """Extract proxy hostname."""
        if self.url:
            return urlparse(self.url).hostname
        return None
    
    @property
    def port(self) -> Optional[int]:
        """Extract proxy port."""
        if self.url:
            return urlparse(self.url).port
        return None


# Proxy Selection Strategies
class ProxySelector(ABC):
    """Abstract base class for proxy selection strategies."""
    
    @abstractmethod
    def select(self, proxies: List[ProxyUrlConfig]) -> ProxyUrlConfig:
        """Select a proxy from the list of available proxies."""
        pass
    
    def record_connection(self, proxy: ProxyUrlConfig) -> None:
        """Record that a connection was made to this proxy (for strategies that track usage)."""
        pass
    
    def record_disconnection(self, proxy: ProxyUrlConfig) -> None:
        """Record that a connection was closed to this proxy (for strategies that track usage)."""
        pass


class RoundRobinSelector(ProxySelector):
    """Round-robin proxy selection strategy."""
    
    def __init__(self):
        self._current_index = 0
    
    def select(self, proxies: List[ProxyUrlConfig]) -> ProxyUrlConfig:
        """Select next proxy in round-robin order."""
        if not proxies:
            raise ValueError("No proxies available for selection")
        
        selected = proxies[self._current_index % len(proxies)]
        self._current_index += 1
        return selected


class RandomSelector(ProxySelector):
    """Random proxy selection strategy."""
    
    def select(self, proxies: List[ProxyUrlConfig]) -> ProxyUrlConfig:
        """Select random proxy from available proxies."""
        if not proxies:
            raise ValueError("No proxies available for selection")
        
        return random.choice(proxies)


class LeastConnectionsSelector(ProxySelector):
    """Least connections proxy selection strategy."""
    
    def __init__(self):
        self._connection_counts: Dict[str, int] = {}
    
    def select(self, proxies: List[ProxyUrlConfig]) -> ProxyUrlConfig:
        """Select proxy with least connections."""
        if not proxies:
            raise ValueError("No proxies available for selection")
        
        # Find proxy with minimum connections
        min_connections = float('inf')
        selected_proxy = proxies[0]
        
        for proxy in proxies:
            connections = self._connection_counts.get(proxy.url, 0)
            if connections < min_connections:
                min_connections = connections
                selected_proxy = proxy
        
        return selected_proxy
    
    def record_connection(self, proxy: ProxyUrlConfig) -> None:
        """Record a new connection to this proxy."""
        self._connection_counts[proxy.url] = self._connection_counts.get(proxy.url, 0) + 1
    
    def record_disconnection(self, proxy: ProxyUrlConfig) -> None:
        """Record a disconnection from this proxy."""
        current = self._connection_counts.get(proxy.url, 0)
        self._connection_counts[proxy.url] = max(0, current - 1)


# Health Checking
class HealthCheckConfig(BaseModel):
    """Health check configuration for proxy pools."""
    model_config = ConfigDict(extra='forbid')
    
    enabled: bool = Field(default=True, description="Enable health checking")
    method: Literal['tcp', 'http', 'ping'] = Field(default='tcp', description="Health check method")
    interval_seconds: int = Field(default=30, ge=5, le=300, description="Check interval in seconds")
    timeout_seconds: int = Field(default=5, ge=1, le=30, description="Check timeout in seconds")
    retry_count: int = Field(default=3, ge=1, le=10, description="Number of retries on failure")


class HealthCheckResult(BaseModel):
    """Result of a health check operation."""
    model_config = ConfigDict(extra='forbid')
    
    healthy: bool = Field(..., description="Whether the proxy is healthy")
    latency: Optional[float] = Field(default=None, description="Latency in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp of check")


class TCPHealthChecker:
    """TCP-based health checker for proxies."""
    
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds
    
    async def check_proxy(self, proxy: ProxyUrlConfig) -> HealthCheckResult:
        """Check proxy health using TCP connection."""
        start_time = datetime.now(UTC)
        
        try:
            # Extract host and port from proxy URL
            parsed = urlparse(proxy.url)
            host = parsed.hostname
            port = parsed.port
            
            if not host or not port:
                return HealthCheckResult(
                    healthy=False,
                    error="Invalid proxy URL - missing host or port",
                    timestamp=start_time
                )
            
            # Attempt TCP connection
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=self.timeout_seconds
                )
                writer.close()
                await writer.wait_closed()
                
                # Calculate latency
                end_time = datetime.now(UTC)
                latency_ms = (end_time - start_time).total_seconds() * 1000
                
                return HealthCheckResult(
                    healthy=True,
                    latency=latency_ms,
                    timestamp=start_time
                )
                
            except asyncio.TimeoutError:
                return HealthCheckResult(
                    healthy=False,
                    error=f"Connection timeout after {self.timeout_seconds}s",
                    timestamp=start_time
                )
            except ConnectionRefusedError:
                return HealthCheckResult(
                    healthy=False,
                    error="Connection refused",
                    timestamp=start_time
                )
            except Exception as e:
                return HealthCheckResult(
                    healthy=False,
                    error=f"Connection error: {str(e)}",
                    timestamp=start_time
                )
                
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                error=f"Health check error: {str(e)}",
                timestamp=start_time
            )


# Proxy Pool Management
class ProxyPool:
    """Proxy pool management with selection strategies and health checking."""
    
    def __init__(self, pool_config: ProxyPoolConfig):
        self.config = pool_config
        self._unhealthy_proxies: set[str] = set()  # Track unhealthy proxy URLs
        
        # Initialize selector based on strategy
        if pool_config.strategy == 'round_robin':
            self._selector = RoundRobinSelector()
        elif pool_config.strategy == 'random':
            self._selector = RandomSelector()
        elif pool_config.strategy == 'least_connections':
            self._selector = LeastConnectionsSelector()
        else:
            raise ValueError(f"Unsupported selection strategy: {pool_config.strategy}")
    
    def get_all_proxies(self) -> List[ProxyUrlConfig]:
        """Get all configured proxies."""
        return self.config.proxies.copy()
    
    def get_healthy_proxies(self) -> List[ProxyUrlConfig]:
        """Get only healthy (enabled and not marked unhealthy) proxies."""
        return [
            proxy for proxy in self.config.proxies 
            if proxy.enabled and proxy.url not in self._unhealthy_proxies
        ]
    
    def select_proxy(self) -> ProxyUrlConfig:
        """Select a proxy using the configured strategy."""
        # Try to select from healthy proxies first
        healthy_proxies = self.get_healthy_proxies()
        
        if healthy_proxies:
            selected = self._selector.select(healthy_proxies)
        else:
            # Fallback to all proxies if no healthy ones available
            all_proxies = [proxy for proxy in self.config.proxies if proxy.enabled]
            if not all_proxies:
                raise RuntimeError("No enabled proxies available")
            selected = self._selector.select(all_proxies)
        
        # Record connection for strategies that track usage
        self._selector.record_connection(selected)
        return selected
    
    def mark_unhealthy(self, proxy: ProxyUrlConfig) -> None:
        """Mark a proxy as unhealthy."""
        self._unhealthy_proxies.add(proxy.url)
    
    def mark_healthy(self, proxy: ProxyUrlConfig) -> None:
        """Mark a proxy as healthy (remove from unhealthy set)."""
        self._unhealthy_proxies.discard(proxy.url)
    
    def is_healthy(self, proxy: ProxyUrlConfig) -> bool:
        """Check if a proxy is considered healthy."""
        return proxy.enabled and proxy.url not in self._unhealthy_proxies


class ConnectionProxies(BaseModel):
    """Proxy configuration for different connection types."""
    model_config = ConfigDict(extra='forbid')
    
    http: Optional[ProxyConfig] = Field(default=None, description="HTTP/REST proxy")
    websocket: Optional[ProxyConfig] = Field(default=None, description="WebSocket proxy")


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

        log_proxy_usage(transport='websocket', exchange_id=exchange_id, proxy_url=proxy_config.url)

        if scheme in ('socks4', 'socks5'):
            try:
                __import__('python_socks')
            except ModuleNotFoundError as exc:
                raise ImportError("python-socks library required for SOCKS proxy support. Install with: pip install python-socks") from exc
        elif scheme in ('http', 'https'):
            header_key = 'extra_headers' if 'extra_headers' in connect_kwargs else 'additional_headers'
            existing_headers = connect_kwargs.get(header_key, {})
            # Copy headers to avoid mutating caller-provided dicts
            headers = dict(existing_headers) if existing_headers else {}
            headers.setdefault('Proxy-Connection', 'keep-alive')
            connect_kwargs[header_key] = headers

        connect_kwargs['proxy'] = proxy_config.url
        return await websockets.connect(url, **connect_kwargs)


# Global proxy injector instance (singleton pattern simplified)
_proxy_injector: Optional[ProxyInjector] = None


def get_proxy_injector() -> Optional[ProxyInjector]:
    """Get global proxy injector instance."""
    return _proxy_injector


def init_proxy_system(settings: ProxySettings) -> None:
    """Initialize proxy system with settings."""
    global _proxy_injector
    if settings.enabled:
        _proxy_injector = ProxyInjector(settings)
    else:
        _proxy_injector = None


def load_proxy_settings() -> ProxySettings:
    """Load proxy settings from environment or configuration."""
    return ProxySettings()


def _proxy_endpoint_components(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.hostname or ''
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return parsed.scheme, host


def log_proxy_usage(*, transport: str, exchange_id: Optional[str], proxy_url: str) -> None:
    scheme, endpoint = _proxy_endpoint_components(proxy_url)
    LOG.info("proxy: transport=%s exchange=%s scheme=%s endpoint=%s", transport, exchange_id or 'default', scheme, endpoint)
