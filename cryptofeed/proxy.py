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
from typing import Optional, Literal, Dict, Any, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


LOG = logging.getLogger('feedhandler')


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
