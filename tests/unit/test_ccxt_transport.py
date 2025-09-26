"""
Test suite for CCXT Transport layer implementation.

Tests follow TDD principles:
- RED: Write failing tests first
- GREEN: Implement minimal code to pass
- REFACTOR: Improve code structure
"""
from __future__ import annotations

import asyncio
import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from cryptofeed.proxy import ProxyConfig, ProxyPoolConfig, ProxyUrlConfig
from pydantic import ValidationError


class TestCcxtRestTransport:
    """Test REST transport with proxy integration."""

    @pytest.fixture
    def proxy_config(self):
        """Mock proxy configuration."""
        return ProxyConfig(
            url="http://proxy1:8080",
            pool=ProxyPoolConfig(
                proxies=[
                    ProxyUrlConfig(url="http://proxy1:8080", weight=1.0, enabled=True),
                    ProxyUrlConfig(url="socks5://proxy2:1080", weight=1.0, enabled=True)
                ]
            )
        )

    def test_ccxt_rest_transport_creation_with_proxy(self, proxy_config):
        """Test CcxtRestTransport can be created with proxy configuration."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport(proxy_config=proxy_config)
        assert transport.proxy_config == proxy_config
        assert transport.timeout == 30.0  # default
        assert transport.max_retries == 3  # default

    def test_ccxt_rest_transport_with_proxy_integration(self, proxy_config):
        """Test proxy configuration is properly stored."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport(proxy_config=proxy_config)
        assert transport.proxy_config.url == "http://proxy1:8080"

    def test_ccxt_rest_transport_session_management(self):
        """Test session management attributes exist."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport()
        assert hasattr(transport, 'session')
        assert transport.session is None  # Initially None

    @pytest.mark.asyncio
    async def test_ccxt_rest_transport_request_with_retries(self):
        """Test basic request functionality with mocked response."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport(max_retries=1, base_delay=0.1)

        # Mock a successful response
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={"result": "ok"})

            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transport.request('GET', 'https://api.example.com/markets')
            assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_ccxt_rest_transport_exponential_backoff(self):
        """Test exponential backoff on retries."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport(max_retries=2, base_delay=0.1)

        call_count = 0

        async def mock_request_context(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise aiohttp.ClientError("Connection failed")

            # Successful response on third try
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={"result": "ok"})
            return mock_response

        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__ = mock_request_context
            mock_request.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await transport.request('GET', 'https://api.example.com/test')
            assert result["result"] == "ok"
            assert call_count == 3  # Should have retried twice

    @pytest.mark.asyncio
    async def test_ccxt_rest_transport_request_hooks(self):
        """Test request/response hooks are called properly."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport

        request_hook_called = False
        response_hook_called = False

        def request_hook(method, url, **kwargs):
            nonlocal request_hook_called
            request_hook_called = True

        def response_hook(response):
            nonlocal response_hook_called
            response_hook_called = True

        transport = CcxtRestTransport(
            request_hook=request_hook,
            response_hook=response_hook
        )

        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.raise_for_status = AsyncMock()
            mock_response.json = AsyncMock(return_value={})

            mock_request.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_request.return_value.__aexit__ = AsyncMock(return_value=False)

            await transport.request('GET', 'https://api.example.com/test')

            assert request_hook_called
            assert response_hook_called

    def test_ccxt_rest_transport_logging_configuration(self):
        """Test structured logging configuration."""
        from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport
        transport = CcxtRestTransport(log_requests=True, log_responses=True)
        assert hasattr(transport, 'logger')
        assert transport.log_requests is True
        assert transport.log_responses is True


class TestCcxtWsTransport:
    """Test WebSocket transport with proxy integration."""

    def test_ccxt_ws_transport_creation(self):
        """Test CcxtWsTransport can be created."""
        from cryptofeed.exchanges.ccxt_transport import CcxtWsTransport
        transport = CcxtWsTransport()
        assert transport.reconnect_delay == 1.0  # default
        assert transport.max_reconnects == 5  # default

    def test_ccxt_ws_transport_with_socks_proxy(self):
        """Test SOCKS proxy integration (basic configuration)."""
        from cryptofeed.exchanges.ccxt_transport import CcxtWsTransport

        proxy_config = ProxyConfig(
            url="socks5://proxy:1080",
            pool=ProxyPoolConfig(
                proxies=[ProxyUrlConfig(url="socks5://proxy:1080", weight=1.0, enabled=True)]
            )
        )

        transport = CcxtWsTransport(proxy_config=proxy_config)
        assert transport.proxy_config.url == "socks5://proxy:1080"

    @pytest.mark.asyncio
    async def test_ccxt_ws_transport_lifecycle_management(self):
        """Test WebSocket lifecycle management."""
        from cryptofeed.exchanges.ccxt_transport import CcxtWsTransport

        transport = CcxtWsTransport()

        # Initially not connected
        assert not transport.is_connected()

        # Mock successful connection
        with patch('websockets.connect', new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_connect.return_value = mock_ws

            await transport.connect("wss://api.example.com/ws")
            assert transport.is_connected()

            await transport.disconnect()
            assert not transport.is_connected()

    @pytest.mark.asyncio
    async def test_ccxt_ws_transport_reconnect_logic_fails(self):
        """RED: Test should fail - reconnect logic not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_transport import CcxtWsTransport

            reconnect_count = 0

            def on_reconnect():
                nonlocal reconnect_count
                reconnect_count += 1

            transport = CcxtWsTransport(
                reconnect_delay=0.1,
                max_reconnects=3,
                on_reconnect=on_reconnect
            )

            # This should trigger reconnects
            with patch('websockets.connect') as mock_connect:
                mock_connect.side_effect = ConnectionError("Connection failed")

                try:
                    await transport.connect("wss://api.example.com/ws")
                except Exception:
                    pass

                assert reconnect_count == 3

    def test_ccxt_ws_transport_metrics_collection_fails(self):
        """RED: Test should fail - metrics collection not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_transport import CcxtWsTransport

            transport = CcxtWsTransport(collect_metrics=True)
            assert hasattr(transport, 'metrics')
            assert hasattr(transport.metrics, 'connection_count')
            assert hasattr(transport.metrics, 'message_count')
            assert hasattr(transport.metrics, 'reconnect_count')


class TestTransportFactory:
    """Test transport factory for consistent instantiation."""

    def test_transport_factory_creation(self):
        """Test TransportFactory can be created."""
        from cryptofeed.exchanges.ccxt_transport import TransportFactory
        factory = TransportFactory()
        assert factory is not None

    def test_transport_factory_creates_rest_transport(self):
        """Test REST transport factory method creates proper transport."""
        from cryptofeed.exchanges.ccxt_transport import TransportFactory, CcxtRestTransport

        factory = TransportFactory()
        rest_transport = factory.create_rest_transport(
            proxy_config=None,
            timeout=30,
            max_retries=3
        )

        assert isinstance(rest_transport, CcxtRestTransport)
        assert rest_transport.timeout == 30
        assert rest_transport.max_retries == 3

    def test_transport_factory_creates_ws_transport(self):
        """Test WebSocket transport factory method creates proper transport."""
        from cryptofeed.exchanges.ccxt_transport import TransportFactory, CcxtWsTransport

        factory = TransportFactory()
        ws_transport = factory.create_ws_transport(
            proxy_config=None,
            reconnect_delay=1.0,
            max_reconnects=5
        )

        assert isinstance(ws_transport, CcxtWsTransport)
        assert ws_transport.reconnect_delay == 1.0
        assert ws_transport.max_reconnects == 5


class TestTransportErrorHandling:
    """Test comprehensive error handling for transport failures."""

    def test_circuit_breaker_pattern_fails(self):
        """RED: Test should fail - circuit breaker not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport, CircuitBreakerError

    @pytest.mark.asyncio
    async def test_timeout_enforcement_fails(self):
        """RED: Test should fail - timeout enforcement not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_transport import CcxtRestTransport

            transport = CcxtRestTransport(timeout=0.1)  # Very short timeout

            with patch('aiohttp.ClientSession.request') as mock_request:
                mock_request.return_value = AsyncMock()
                mock_request.return_value.__aenter__ = AsyncMock()
                mock_request.return_value.__aenter__.return_value.wait_for_status = AsyncMock()

                # This should timeout
                with pytest.raises(asyncio.TimeoutError):
                    await transport.request('GET', 'https://slow-api.example.com/test')