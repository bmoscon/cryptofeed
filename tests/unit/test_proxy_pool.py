"""
Test suite for proxy pool functionality extending the existing proxy system.

Following TDD methodology - tests written first to drive implementation.
"""
import pytest
from typing import List
from cryptofeed.proxy import ProxyConfig, ConnectionProxies


class TestProxyPoolConfig:
    """Test proxy pool configuration model extensions."""
    
    def test_single_proxy_config_unchanged(self):
        """Test that existing single proxy configuration continues to work unchanged."""
        # Existing single proxy configuration should work exactly as before
        config = ProxyConfig(url="socks5://proxy:1080", timeout_seconds=30)
        assert config.url == "socks5://proxy:1080"
        assert config.timeout_seconds == 30
        assert config.scheme == "socks5"
        assert config.host == "proxy"
        assert config.port == 1080
    
    def test_proxy_pool_config_creation(self):
        """Test creation of proxy configuration with pool support."""
        # This test will drive the implementation of pool configuration
        from cryptofeed.proxy import ProxyPoolConfig, ProxyUrlConfig
        
        pool_config = ProxyPoolConfig(
            proxies=[
                ProxyUrlConfig(url="socks5://proxy1:1080"),
                ProxyUrlConfig(url="socks5://proxy2:1080"),
                ProxyUrlConfig(url="socks5://proxy3:1080")
            ],
            strategy="round_robin"
        )
        
        assert len(pool_config.proxies) == 3
        assert pool_config.strategy == "round_robin"
        assert pool_config.proxies[0].url == "socks5://proxy1:1080"
    
    def test_proxy_url_config_validation(self):
        """Test individual proxy URL configuration within pools."""
        from cryptofeed.proxy import ProxyUrlConfig
        
        # Valid proxy URL config
        proxy_url = ProxyUrlConfig(url="socks5://proxy:1080", weight=1.0, enabled=True)
        assert proxy_url.url == "socks5://proxy:1080"
        assert proxy_url.weight == 1.0
        assert proxy_url.enabled is True
        
        # Default values
        proxy_url_defaults = ProxyUrlConfig(url="http://proxy:8080")
        assert proxy_url_defaults.weight == 1.0  # Default weight
        assert proxy_url_defaults.enabled is True  # Default enabled
    
    def test_invalid_proxy_url_in_pool(self):
        """Test validation of invalid proxy URLs in pool configuration."""
        from cryptofeed.proxy import ProxyUrlConfig
        
        with pytest.raises(ValueError, match="Proxy URL must include scheme"):
            ProxyUrlConfig(url="invalid-url")
    
    def test_proxy_config_with_pool_field(self):
        """Test ProxyConfig extended with pool field."""
        from cryptofeed.proxy import ProxyPoolConfig, ProxyUrlConfig
        
        # Test that ProxyConfig can have either url OR pool, but not both
        
        # Single proxy config (existing behavior)
        single_config = ProxyConfig(url="socks5://proxy:1080")
        assert single_config.url == "socks5://proxy:1080"
        assert not hasattr(single_config, 'pool') or single_config.pool is None
        
        # Pool config (new behavior) - this will drive pool field implementation
        pool = ProxyPoolConfig(
            proxies=[ProxyUrlConfig(url="socks5://proxy1:1080")],
            strategy="round_robin"
        )
        
        pool_config = ProxyConfig(pool=pool)
        assert pool_config.pool is not None
        assert not hasattr(pool_config, 'url') or pool_config.url is None


class TestProxyPoolSelection:
    """Test proxy pool selection strategies."""
    
    def test_round_robin_selector(self):
        """Test round-robin proxy selection strategy."""
        from cryptofeed.proxy import RoundRobinSelector, ProxyUrlConfig
        
        proxies = [
            ProxyUrlConfig(url="socks5://proxy1:1080"),
            ProxyUrlConfig(url="socks5://proxy2:1080"), 
            ProxyUrlConfig(url="socks5://proxy3:1080")
        ]
        
        selector = RoundRobinSelector()
        
        # First calls should cycle through proxies
        selected1 = selector.select(proxies)
        selected2 = selector.select(proxies)
        selected3 = selector.select(proxies)
        selected4 = selector.select(proxies)  # Should wrap around
        
        assert selected1.url == "socks5://proxy1:1080"
        assert selected2.url == "socks5://proxy2:1080"
        assert selected3.url == "socks5://proxy3:1080"
        assert selected4.url == "socks5://proxy1:1080"  # Wrapped around
    
    def test_random_selector(self):
        """Test random proxy selection strategy."""
        from cryptofeed.proxy import RandomSelector, ProxyUrlConfig
        
        proxies = [
            ProxyUrlConfig(url="socks5://proxy1:1080"),
            ProxyUrlConfig(url="socks5://proxy2:1080")
        ]
        
        selector = RandomSelector()
        
        # Random selection should return one of the proxies
        selected = selector.select(proxies)
        assert selected.url in ["socks5://proxy1:1080", "socks5://proxy2:1080"]
    
    def test_least_connections_selector(self):
        """Test least connections proxy selection strategy."""
        from cryptofeed.proxy import LeastConnectionsSelector, ProxyUrlConfig
        
        proxies = [
            ProxyUrlConfig(url="socks5://proxy1:1080"),
            ProxyUrlConfig(url="socks5://proxy2:1080")
        ]
        
        selector = LeastConnectionsSelector()
        
        # Initially should select first proxy (no connections)
        selected1 = selector.select(proxies)
        assert selected1.url == "socks5://proxy1:1080"
        
        # Record connection to first proxy
        selector.record_connection(selected1)
        
        # Next selection should prefer proxy with fewer connections
        selected2 = selector.select(proxies)
        assert selected2.url == "socks5://proxy2:1080"


class TestHealthChecker:
    """Test health checking functionality."""
    
    def test_health_check_config(self):
        """Test health check configuration."""
        from cryptofeed.proxy import HealthCheckConfig
        
        config = HealthCheckConfig(
            enabled=True,
            method="tcp",
            interval_seconds=30,
            timeout_seconds=5,
            retry_count=3
        )
        
        assert config.enabled is True
        assert config.method == "tcp"
        assert config.interval_seconds == 30
        assert config.timeout_seconds == 5
        assert config.retry_count == 3
    
    @pytest.mark.asyncio
    async def test_tcp_health_check(self):
        """Test TCP health check implementation."""
        from cryptofeed.proxy import TCPHealthChecker, ProxyUrlConfig
        
        proxy = ProxyUrlConfig(url="socks5://proxy:1080")
        checker = TCPHealthChecker(timeout_seconds=5)
        
        # This will initially fail since we don't have a real proxy
        # but it drives the interface design
        result = await checker.check_proxy(proxy)
        
        assert hasattr(result, 'healthy')
        assert hasattr(result, 'latency')
        assert hasattr(result, 'error')
        assert hasattr(result, 'timestamp')


class TestProxyPool:
    """Test proxy pool management."""
    
    def test_proxy_pool_creation(self):
        """Test proxy pool creation and basic functionality."""
        from cryptofeed.proxy import ProxyPool, ProxyPoolConfig, ProxyUrlConfig
        
        pool_config = ProxyPoolConfig(
            proxies=[
                ProxyUrlConfig(url="socks5://proxy1:1080"),
                ProxyUrlConfig(url="socks5://proxy2:1080")
            ],
            strategy="round_robin"
        )
        
        pool = ProxyPool(pool_config)
        assert len(pool.get_all_proxies()) == 2
        
        # Test proxy selection
        selected = pool.select_proxy()
        assert selected.url in ["socks5://proxy1:1080", "socks5://proxy2:1080"]
    
    def test_proxy_pool_health_filtering(self):
        """Test proxy pool filtering based on health status."""
        from cryptofeed.proxy import ProxyPool, ProxyPoolConfig, ProxyUrlConfig
        
        pool_config = ProxyPoolConfig(
            proxies=[
                ProxyUrlConfig(url="socks5://proxy1:1080"),
                ProxyUrlConfig(url="socks5://proxy2:1080")
            ],
            strategy="round_robin"
        )
        
        pool = ProxyPool(pool_config)
        
        # Initially all proxies should be available
        healthy_proxies = pool.get_healthy_proxies()
        assert len(healthy_proxies) == 2
        
        # Mark one proxy as unhealthy
        proxy1 = pool.get_all_proxies()[0]
        pool.mark_unhealthy(proxy1)
        
        # Should now only return healthy proxies
        healthy_proxies = pool.get_healthy_proxies()
        assert len(healthy_proxies) == 1
        assert healthy_proxies[0].url == "socks5://proxy2:1080"


class TestBackwardCompatibility:
    """Test that proxy pool extensions don't break existing functionality."""
    
    def test_existing_connection_proxies_unchanged(self):
        """Test that ConnectionProxies continues to work with single proxies."""
        # Existing configuration should work unchanged
        proxies = ConnectionProxies(
            http=ProxyConfig(url="http://proxy:8080"),
            websocket=ProxyConfig(url="socks5://proxy:1081")
        )
        
        assert proxies.http.url == "http://proxy:8080"
        assert proxies.websocket.url == "socks5://proxy:1081"
    
    def test_connection_proxies_with_pools(self):
        """Test ConnectionProxies extended to support pools."""
        from cryptofeed.proxy import ProxyPoolConfig, ProxyUrlConfig
        
        # Pool configuration for HTTP
        http_pool = ProxyPoolConfig(
            proxies=[
                ProxyUrlConfig(url="http://proxy1:8080"),
                ProxyUrlConfig(url="http://proxy2:8080")
            ],
            strategy="round_robin"
        )
        
        # Single proxy for WebSocket
        websocket_single = ProxyConfig(url="socks5://ws-proxy:1081")
        
        # ConnectionProxies should support mixing pools and single proxies
        proxies = ConnectionProxies(
            http=ProxyConfig(pool=http_pool),
            websocket=websocket_single
        )
        
        assert proxies.http.pool is not None
        assert len(proxies.http.pool.proxies) == 2
        assert proxies.websocket.url == "socks5://ws-proxy:1081"