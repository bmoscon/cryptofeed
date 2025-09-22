"""
Integration tests for Proxy MVP with real-world scenarios.

Following engineering principles from CLAUDE.md:
- TDD: Test real integration scenarios 
- NO MOCKS: Use real implementations for integration testing
- START SMALL: Test MVP scenarios only
- PRACTICAL: Focus on real-world usage patterns
"""
import pytest
import asyncio
import os
from typing import Optional

from cryptofeed.proxy import (
    ProxySettings, 
    ProxyConfig, 
    ConnectionProxies,
    init_proxy_system,
    get_proxy_injector,
    load_proxy_settings
)
from cryptofeed.connection import HTTPAsyncConn, WSAsyncConn


class TestProxyConfigurationLoading:
    """Test proxy configuration loading from environment and files."""
    
    def test_environment_variable_configuration(self):
        """Test loading proxy configuration from environment variables."""
        # Set environment variables
        os.environ["CRYPTOFEED_PROXY_ENABLED"] = "true"
        os.environ["CRYPTOFEED_PROXY_DEFAULT__HTTP__URL"] = "socks5://test-proxy:1080"
        os.environ["CRYPTOFEED_PROXY_DEFAULT__HTTP__TIMEOUT_SECONDS"] = "15"
        os.environ["CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL"] = "http://binance-proxy:8080"
        
        try:
            settings = load_proxy_settings()
            
            assert settings.enabled
            assert settings.default.http.url == "socks5://test-proxy:1080"
            assert settings.default.http.timeout_seconds == 15
            assert "binance" in settings.exchanges
            assert settings.exchanges["binance"].http.url == "http://binance-proxy:8080"
            
        finally:
            # Clean up environment variables
            for key in ["CRYPTOFEED_PROXY_ENABLED", 
                       "CRYPTOFEED_PROXY_DEFAULT__HTTP__URL",
                       "CRYPTOFEED_PROXY_DEFAULT__HTTP__TIMEOUT_SECONDS",
                       "CRYPTOFEED_PROXY_EXCHANGES__BINANCE__HTTP__URL"]:
                os.environ.pop(key, None)
    
    def test_programmatic_configuration(self):
        """Test programmatic proxy configuration."""
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://company-proxy:1080"),
                websocket=ProxyConfig(url="socks5://company-proxy:1081")
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://binance-specific:8080", timeout_seconds=10)
                ),
                "coinbase": ConnectionProxies(
                    websocket=ProxyConfig(url="socks5://coinbase-ws:1081")
                )
            }
        )
        
        # Test exchange-specific resolution
        assert settings.get_proxy("binance", "http").url == "http://binance-specific:8080"
        assert settings.get_proxy("binance", "http").timeout_seconds == 10
        
        # Test default fallback
        assert settings.get_proxy("binance", "websocket").url == "socks5://company-proxy:1081"
        assert settings.get_proxy("unknown_exchange", "http").url == "socks5://company-proxy:1080"
        
        # Test exchange-specific WebSocket
        assert settings.get_proxy("coinbase", "websocket").url == "socks5://coinbase-ws:1081"
        
        # Test missing configuration
        assert settings.get_proxy("coinbase", "http").url == "socks5://company-proxy:1080"


class TestProxySystemIntegration:
    """Test complete proxy system integration."""
    
    @pytest.fixture
    def production_proxy_settings(self):
        """Realistic proxy configuration for production use."""
        return ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://corporate-proxy.company.com:1080", timeout_seconds=30),
                websocket=ProxyConfig(url="socks5://corporate-proxy.company.com:1081", timeout_seconds=30)
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://region-asia.proxy.company.com:8080", timeout_seconds=15),
                    websocket=ProxyConfig(url="socks5://region-asia.proxy.company.com:1081", timeout_seconds=15)
                ),
                "coinbase": ConnectionProxies(
                    http=ProxyConfig(url="http://region-us.proxy.company.com:8080", timeout_seconds=10)
                    # WebSocket uses default proxy
                ),
                "backpack": ConnectionProxies(
                    # Only WebSocket override, HTTP uses default
                    websocket=ProxyConfig(url="socks5://backpack-proxy.company.com:1080", timeout_seconds=20)
                )
            }
        )
    
    def test_proxy_system_initialization(self, production_proxy_settings):
        """Test proxy system initialization and global state."""
        # Test disabled state
        init_proxy_system(ProxySettings(enabled=False))
        assert get_proxy_injector() is None
        
        # Test enabled state
        init_proxy_system(production_proxy_settings)
        injector = get_proxy_injector()
        assert injector is not None
        assert injector.settings == production_proxy_settings
        
        # Test proxy resolution through injector
        assert injector.get_http_proxy_url("binance") == "http://region-asia.proxy.company.com:8080"
        assert injector.get_http_proxy_url("coinbase") == "http://region-us.proxy.company.com:8080"
        assert injector.get_http_proxy_url("backpack") == "socks5://corporate-proxy.company.com:1080"
        assert injector.get_http_proxy_url("unknown") == "socks5://corporate-proxy.company.com:1080"
    
    @pytest.mark.asyncio
    async def test_http_connection_with_proxy_system(self, production_proxy_settings):
        """Test HTTP connection integration with proxy system."""
        init_proxy_system(production_proxy_settings)
        
        try:
            # Test connection with exchange-specific proxy
            conn_binance = HTTPAsyncConn("test-binance", exchange_id="binance")
            await conn_binance._open()
            
            assert conn_binance.is_open
            assert conn_binance.exchange_id == "binance"
            assert conn_binance.proxy == "http://region-asia.proxy.company.com:8080"
            assert str(conn_binance.conn._default_proxy) == "http://region-asia.proxy.company.com:8080"
            
            # Test connection with default proxy fallback
            conn_unknown = HTTPAsyncConn("test-unknown", exchange_id="unknown_exchange")
            await conn_unknown._open()
            
            assert conn_unknown.is_open
            assert conn_unknown.exchange_id == "unknown_exchange"
            assert conn_unknown.proxy == "socks5://corporate-proxy.company.com:1080"
            assert str(conn_unknown.conn._default_proxy) == "socks5://corporate-proxy.company.com:1080"
            
            # Test connection without exchange_id (no proxy)
            conn_no_proxy = HTTPAsyncConn("test-no-proxy")
            await conn_no_proxy._open()
            
            assert conn_no_proxy.is_open
            assert conn_no_proxy.exchange_id is None
            assert conn_no_proxy.proxy is None
            assert conn_no_proxy.conn._default_proxy is None
            
        finally:
            # Clean up connections
            for conn in [conn_binance, conn_unknown, conn_no_proxy]:
                if conn.is_open:
                    await conn.close()
            
            # Reset proxy system
            init_proxy_system(ProxySettings(enabled=False))
    
    def test_websocket_connection_with_proxy_system(self, production_proxy_settings):
        """Test WebSocket connection integration with proxy system."""
        init_proxy_system(production_proxy_settings)
        
        try:
            # Test connection creation with different proxy configurations
            conn_binance = WSAsyncConn("wss://stream.binance.com:9443/ws", "test-binance", exchange_id="binance")
            assert conn_binance.exchange_id == "binance"
            
            conn_backpack = WSAsyncConn("wss://ws.backpack.exchange", "test-backpack", exchange_id="backpack") 
            assert conn_backpack.exchange_id == "backpack"
            
            conn_no_proxy = WSAsyncConn("wss://example.com", "test-no-proxy")
            assert conn_no_proxy.exchange_id is None
            
        finally:
            # Reset proxy system
            init_proxy_system(ProxySettings(enabled=False))


class TestProxyErrorHandling:
    """Test proxy system error handling and edge cases."""
    
    def test_invalid_proxy_configurations(self):
        """Test handling of invalid proxy configurations."""
        # Test invalid URL scheme
        with pytest.raises(ValueError, match="Unsupported proxy scheme"):
            ProxyConfig(url="ftp://invalid:1080")
        
        # Test missing scheme
        with pytest.raises(ValueError, match="Proxy URL must include scheme"):
            ProxyConfig(url="proxy.example.com:1080")
        
        # Test missing hostname
        with pytest.raises(ValueError, match="Proxy URL must include hostname"):
            ProxyConfig(url="socks5://:1080")
        
        # Test missing port
        with pytest.raises(ValueError, match="Proxy URL must include port"):
            ProxyConfig(url="socks5://proxy.example.com")
        
        # Test invalid timeout range
        with pytest.raises(ValueError):
            ProxyConfig(url="socks5://proxy:1080", timeout_seconds=0)
        
        with pytest.raises(ValueError):
            ProxyConfig(url="socks5://proxy:1080", timeout_seconds=301)
    
    @pytest.mark.asyncio
    async def test_connection_without_proxy_system(self):
        """Test connections work correctly when proxy system is disabled."""
        # Ensure proxy system is disabled
        init_proxy_system(ProxySettings(enabled=False))
        
        # HTTP connection should work without proxy
        http_conn = HTTPAsyncConn("test-http", exchange_id="binance")
        await http_conn._open()
        
        assert http_conn.is_open
        assert get_proxy_injector() is None
        
        await http_conn.close()
        
        # WebSocket connection should work without proxy
        ws_conn = WSAsyncConn("wss://example.com", "test-ws", exchange_id="binance")
        assert ws_conn.exchange_id == "binance"
        
        # Note: Not opening WebSocket connection as it would try to connect to real server


class TestProxyConfigurationPatterns:
    """Test common proxy configuration patterns."""
    
    def test_development_environment_pattern(self):
        """Test typical development environment proxy configuration."""
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="http://localhost:8888"),  # Local proxy for development
                websocket=ProxyConfig(url="socks5://localhost:1080")
            )
        )
        
        assert settings.get_proxy("any_exchange", "http").url == "http://localhost:8888"
        assert settings.get_proxy("any_exchange", "websocket").url == "socks5://localhost:1080"
    
    def test_production_regional_pattern(self):
        """Test production environment with regional proxy routing."""
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://proxy-global.company.com:1080", timeout_seconds=30)
            ),
            exchanges={
                # US exchanges through US proxy
                "coinbase": ConnectionProxies(
                    http=ProxyConfig(url="http://proxy-us.company.com:8080", timeout_seconds=15),
                    websocket=ProxyConfig(url="socks5://proxy-us.company.com:1081", timeout_seconds=15)
                ),
                "kraken": ConnectionProxies(
                    http=ProxyConfig(url="http://proxy-us.company.com:8080", timeout_seconds=15),
                    websocket=ProxyConfig(url="socks5://proxy-us.company.com:1081", timeout_seconds=15)
                ),
                
                # Asian exchanges through Asian proxy
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://proxy-asia.company.com:8080", timeout_seconds=20),
                    websocket=ProxyConfig(url="socks5://proxy-asia.company.com:1081", timeout_seconds=20)
                ),
                "backpack": ConnectionProxies(
                    http=ProxyConfig(url="http://proxy-asia.company.com:8080", timeout_seconds=20),
                    websocket=ProxyConfig(url="socks5://proxy-asia.company.com:1081", timeout_seconds=20)
                ),
                
                # European exchanges through European proxy
                "bitstamp": ConnectionProxies(
                    http=ProxyConfig(url="http://proxy-eu.company.com:8080", timeout_seconds=25),
                    websocket=ProxyConfig(url="socks5://proxy-eu.company.com:1081", timeout_seconds=25)
                )
            }
        )
        
        # Test regional routing
        assert "proxy-us.company.com" in settings.get_proxy("coinbase", "http").url
        assert "proxy-asia.company.com" in settings.get_proxy("binance", "http").url  
        assert "proxy-eu.company.com" in settings.get_proxy("bitstamp", "http").url
        
        # Test global fallback
        assert "proxy-global.company.com" in settings.get_proxy("unknown_exchange", "http").url
    
    def test_high_frequency_trading_pattern(self):
        """Test configuration optimized for high-frequency trading."""
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://fast-proxy.hft.com:1080", timeout_seconds=5),
                websocket=ProxyConfig(url="socks5://fast-proxy.hft.com:1081", timeout_seconds=5)
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="socks5://binance-direct.hft.com:1080", timeout_seconds=3),
                    websocket=ProxyConfig(url="socks5://binance-direct.hft.com:1081", timeout_seconds=3)
                ),
                "coinbase": ConnectionProxies(
                    http=ProxyConfig(url="socks5://coinbase-direct.hft.com:1080", timeout_seconds=3),
                    websocket=ProxyConfig(url="socks5://coinbase-direct.hft.com:1081", timeout_seconds=3)
                )
            }
        )
        
        # Test low timeout configurations for HFT
        assert settings.get_proxy("binance", "http").timeout_seconds == 3
        assert settings.get_proxy("coinbase", "websocket").timeout_seconds == 3
        assert settings.get_proxy("other", "http").timeout_seconds == 5


@pytest.mark.integration
class TestRealWorldUsageExamples:
    """Examples showing how to use the proxy system in real applications."""
    
    def test_yaml_configuration_example(self):
        """Example of YAML configuration that users would write."""
        # This simulates loading from a YAML file
        yaml_config = {
            "enabled": True,
            "default": {
                "http": {
                    "url": "socks5://corporate-proxy:1080",
                    "timeout_seconds": 30
                },
                "websocket": {
                    "url": "socks5://corporate-proxy:1081", 
                    "timeout_seconds": 30
                }
            },
            "exchanges": {
                "binance": {
                    "http": {
                        "url": "http://region-asia.proxy:8080",
                        "timeout_seconds": 15
                    }
                },
                "coinbase": {
                    "http": {
                        "url": "http://region-us.proxy:8080",
                        "timeout_seconds": 10
                    }
                }
            }
        }
        
        # Convert to ProxySettings (in real usage, this would be done by pydantic-settings)
        settings = ProxySettings(**yaml_config)
        
        # Verify configuration loaded correctly
        assert settings.enabled
        assert settings.default.http.url == "socks5://corporate-proxy:1080"
        assert settings.exchanges["binance"].http.timeout_seconds == 15
    
    @pytest.mark.asyncio
    async def test_complete_usage_example(self):
        """Complete example showing proxy system usage from configuration to connection."""
        # 1. Create proxy configuration
        settings = ProxySettings(
            enabled=True,
            default=ConnectionProxies(
                http=ProxyConfig(url="socks5://example-proxy:1080")
            ),
            exchanges={
                "binance": ConnectionProxies(
                    http=ProxyConfig(url="http://binance-proxy:8080")
                )
            }
        )
        
        # 2. Initialize proxy system 
        init_proxy_system(settings)
        
        try:
            # 3. Create connections - proxy is applied transparently
            binance_conn = HTTPAsyncConn("binance-api", exchange_id="binance")
            coinbase_conn = HTTPAsyncConn("coinbase-api", exchange_id="coinbase")
            
            # 4. Open connections - proxy configuration is applied automatically
            await binance_conn._open()
            await coinbase_conn._open()
            
            # 5. Verify connections are open and configured correctly
            assert binance_conn.is_open
            assert coinbase_conn.is_open
            
            # 6. Verify proxy injector knows about the exchanges
            injector = get_proxy_injector()
            assert injector.get_http_proxy_url("binance") == "http://binance-proxy:8080"
            assert injector.get_http_proxy_url("coinbase") == "socks5://example-proxy:1080"
            
        finally:
            # 7. Clean up
            if binance_conn.is_open:
                await binance_conn.close()
            if coinbase_conn.is_open:
                await coinbase_conn.close()
            
            # 8. Reset proxy system
            init_proxy_system(ProxySettings(enabled=False))
