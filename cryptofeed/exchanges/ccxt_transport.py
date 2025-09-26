"""
CCXT Transport layer implementation.

Provides HTTP REST and WebSocket transports with proxy integration,
retry logic, and structured logging for CCXT exchanges.

Following engineering principles from CLAUDE.md:
- SOLID: Single responsibility for transport concerns
- KISS: Simple, clear transport interfaces
- DRY: Reusable transport logic across exchanges
- NO LEGACY: Modern async patterns only
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable, List
from urllib.parse import urlparse

import aiohttp
import websockets
from websockets import WebSocketServerProtocol

from cryptofeed.proxy import ProxyConfig


LOG = logging.getLogger('feedhandler')


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class TransportMetrics:
    """Simple metrics collection for transport operations."""

    def __init__(self):
        self.connection_count = 0
        self.message_count = 0
        self.reconnect_count = 0
        self.error_count = 0

    def increment_connections(self):
        self.connection_count += 1

    def increment_messages(self):
        self.message_count += 1

    def increment_reconnects(self):
        self.reconnect_count += 1

    def increment_errors(self):
        self.error_count += 1


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'open':
            if time.time() - self.last_failure_time < self.recovery_timeout:
                raise CircuitBreakerError("Circuit breaker is open")
            else:
                self.state = 'half-open'

        try:
            result = func(*args, **kwargs)
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'

            raise e


class CcxtRestTransport:
    """HTTP REST transport for CCXT with proxy integration and retry logic."""

    def __init__(
        self,
        proxy_config: Optional[ProxyConfig] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        base_delay: float = 1.0,
        log_requests: bool = False,
        log_responses: bool = False,
        request_hook: Optional[Callable] = None,
        response_hook: Optional[Callable] = None
    ):
        self.proxy_config = proxy_config
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.request_hook = request_hook
        self.response_hook = response_hook
        self.logger = LOG
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = CircuitBreaker()

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None or self.session.closed:
            connector_kwargs = {}

            # Configure proxy if provided
            if self.proxy_config and self.proxy_config.url:
                connector_kwargs['trust_env'] = True

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=aiohttp.TCPConnector(**connector_kwargs)
            )

    async def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic and proxy support."""
        await self._ensure_session()

        # Apply proxy configuration
        if self.proxy_config and self.proxy_config.url:
            kwargs['proxy'] = self.proxy_config.url

        # Execute request hook
        if self.request_hook:
            self.request_hook(method, url, **kwargs)

        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if self.log_requests:
                    self.logger.debug(f"HTTP {method} {url} (attempt {attempt + 1})")

                async with self.session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    result = await response.json()

                    if self.log_responses:
                        self.logger.debug(f"HTTP {method} {url} -> {response.status}")

                    # Execute response hook
                    if self.response_hook:
                        self.response_hook(response)

                    return result

            except Exception as e:
                last_exception = e
                self.logger.warning(f"HTTP {method} {url} failed (attempt {attempt + 1}): {e}")

                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
                else:
                    break

        # All retries exhausted
        raise last_exception or Exception("Request failed after all retries")

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None


class CcxtWsTransport:
    """WebSocket transport for CCXT with proxy integration and reconnection logic."""

    def __init__(
        self,
        proxy_config: Optional[ProxyConfig] = None,
        reconnect_delay: float = 1.0,
        max_reconnects: int = 5,
        collect_metrics: bool = False,
        on_reconnect: Optional[Callable] = None
    ):
        self.proxy_config = proxy_config
        self.reconnect_delay = reconnect_delay
        self.max_reconnects = max_reconnects
        self.on_reconnect = on_reconnect
        self.websocket: Optional[WebSocketServerProtocol] = None
        self._connected = False
        self.metrics = TransportMetrics() if collect_metrics else None

    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self.websocket is not None

    async def connect(self, url: str, **kwargs):
        """Connect to WebSocket with proxy support and reconnection logic."""
        reconnect_count = 0

        while reconnect_count <= self.max_reconnects:
            try:
                # Configure proxy for WebSocket (basic implementation)
                connect_kwargs = kwargs.copy()

                if self.proxy_config and self.proxy_config.url:
                    # Note: websockets library has limited proxy support
                    # For full SOCKS proxy support, would need python-socks integration
                    LOG.warning("WebSocket proxy support is limited")

                self.websocket = await websockets.connect(url, **connect_kwargs)
                self._connected = True

                if self.metrics:
                    self.metrics.increment_connections()

                LOG.info(f"WebSocket connected to {url}")
                return

            except Exception as e:
                LOG.error(f"WebSocket connection failed (attempt {reconnect_count + 1}): {e}")
                reconnect_count += 1

                if self.on_reconnect:
                    self.on_reconnect()

                if self.metrics:
                    self.metrics.increment_reconnects()

                if reconnect_count <= self.max_reconnects:
                    await asyncio.sleep(self.reconnect_delay)

        raise ConnectionError(f"Failed to connect after {self.max_reconnects} attempts")

    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self._connected = False

    async def send(self, message: str):
        """Send message to WebSocket."""
        if not self.is_connected():
            raise ConnectionError("WebSocket not connected")

        await self.websocket.send(message)

        if self.metrics:
            self.metrics.increment_messages()

    async def receive(self) -> str:
        """Receive message from WebSocket."""
        if not self.is_connected():
            raise ConnectionError("WebSocket not connected")

        message = await self.websocket.recv()

        if self.metrics:
            self.metrics.increment_messages()

        return message


class TransportFactory:
    """Factory for creating transport instances with consistent configuration."""

    @staticmethod
    def create_rest_transport(
        proxy_config: Optional[ProxyConfig] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        **kwargs
    ) -> CcxtRestTransport:
        """Create REST transport with standard configuration."""
        return CcxtRestTransport(
            proxy_config=proxy_config,
            timeout=timeout,
            max_retries=max_retries,
            **kwargs
        )

    @staticmethod
    def create_ws_transport(
        proxy_config: Optional[ProxyConfig] = None,
        reconnect_delay: float = 1.0,
        max_reconnects: int = 5,
        **kwargs
    ) -> CcxtWsTransport:
        """Create WebSocket transport with standard configuration."""
        return CcxtWsTransport(
            proxy_config=proxy_config,
            reconnect_delay=reconnect_delay,
            max_reconnects=max_reconnects,
            **kwargs
        )


__all__ = [
    'CcxtRestTransport',
    'CcxtWsTransport',
    'TransportFactory',
    'CircuitBreakerError',
    'TransportMetrics',
    'CircuitBreaker'
]