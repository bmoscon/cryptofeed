"""
Test suite for CCXT Exchange Builder Factory.

Tests follow TDD principles:
- RED: Write failing tests first
- GREEN: Implement minimal code to pass
- REFACTOR: Improve code structure

Tests Task 4.1 acceptance criteria:
- Factory generates feed classes for valid CCXT exchange IDs
- Symbol normalization allows exchange-specific mapping
- Subscription filters enable channel-specific customization
- Generated classes integrate seamlessly with FeedHandler
"""
from __future__ import annotations

import pytest
from typing import Dict, Any, Optional, List, Callable
from unittest.mock import Mock, MagicMock, patch

from cryptofeed.feed import Feed


class TestCcxtExchangeBuilder:
    """Test CCXT exchange builder factory."""

    def test_exchange_builder_creation(self):
        """Test exchange builder can be created."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        builder = CcxtExchangeBuilder()
        assert builder is not None

    def test_exchange_builder_valid_exchange_id(self):
        """Test exchange ID validation with valid and invalid IDs."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()

        # Should validate exchange ID exists in CCXT
        assert builder.validate_exchange_id('binance') is True
        assert builder.validate_exchange_id('invalid_exchange') is False

    def test_exchange_builder_ccxt_module_loading(self):
        """Test CCXT module loading for valid exchanges."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()

        # Should load CCXT modules dynamically
        async_module = builder.load_ccxt_async_module('binance')
        pro_module = builder.load_ccxt_pro_module('binance')

        assert async_module is not None
        assert pro_module is not None

    def test_exchange_builder_feed_class_generation(self):
        """Test feed class generation for valid exchanges."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()

        # Should generate feed class for valid exchange
        feed_class = builder.create_feed_class('binance')

        assert feed_class is not None
        assert issubclass(feed_class, Feed)
        assert feed_class.__name__ == 'BinanceCcxtFeed'

    def test_exchange_builder_symbol_normalization_hook(self):
        """Test symbol normalization hook with custom normalizer."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        def custom_symbol_normalizer(symbol: str) -> str:
            # Custom normalization for specific exchange
            return symbol.upper().replace('_', '-')

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class(
            exchange_id='binance',
            symbol_normalizer=custom_symbol_normalizer
        )

        # Should use custom normalizer
        instance = feed_class()
        normalized = instance.normalize_symbol('btc_usdt')
        assert normalized == 'BTC-USDT'

    def test_exchange_builder_subscription_filters(self):
        """Test subscription filters for channel-specific customization."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.defines import TRADES, L2_BOOK

        def trade_filter(symbol: str, channel: str) -> bool:
            # Only allow trades for BTC pairs
            return channel == TRADES and 'BTC' in symbol

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class(
            exchange_id='binance',
            subscription_filter=trade_filter
        )

        # Should apply filter during subscription
        instance = feed_class()
        assert instance.should_subscribe('BTC-USDT', TRADES) is True
        assert instance.should_subscribe('ETH-USDT', TRADES) is False

    def test_exchange_builder_endpoint_override(self):
        """Test endpoint override functionality."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        custom_endpoints = {
            'rest': 'https://custom-api.binance.com',
            'websocket': 'wss://custom-stream.binance.com'
        }

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class(
            exchange_id='binance',
            endpoint_overrides=custom_endpoints
        )

        instance = feed_class()
        assert instance.rest_endpoint == 'https://custom-api.binance.com'
        assert instance.ws_endpoint == 'wss://custom-stream.binance.com'


class TestExchangeIDValidation:
    """Test exchange ID validation and CCXT integration."""

    def test_ccxt_exchange_list_loading(self):
        """Test loading CCXT exchange list."""
        from cryptofeed.exchanges.ccxt_generic import get_supported_ccxt_exchanges

        exchanges = get_supported_ccxt_exchanges()
        assert isinstance(exchanges, list)
        assert 'binance' in exchanges
        assert 'coinbase' in exchanges

    def test_exchange_id_normalization(self):
        """Test exchange ID normalization for common cases."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()

        # Should normalize common exchange names
        assert builder.normalize_exchange_id('Binance') == 'binance'
        assert builder.normalize_exchange_id('coinbase-pro') == 'coinbasepro'
        assert builder.normalize_exchange_id('HUOBI_PRO') == 'huobipro'

    def test_exchange_feature_detection(self):
        """Test exchange feature detection for capabilities."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()

        # Should detect exchange capabilities
        features = builder.get_exchange_features('binance')
        assert 'trades' in features
        assert 'orderbook' in features
        assert 'websocket' in features


class TestGeneratedFeedClass:
    """Test generated feed class functionality."""

    def test_generated_feed_inheritance(self):
        """Test generated feed class inheritance from Feed."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.feed import Feed

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        # Should properly inherit from Feed
        assert issubclass(feed_class, Feed)

        # Should have proper class attributes
        instance = feed_class()
        assert hasattr(instance, 'id')
        assert hasattr(instance, 'exchange')
        assert instance.exchange == 'binance'

    def test_generated_feed_symbol_handling(self):
        """Test generated feed symbol handling and normalization."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        instance = feed_class()

        # Should handle symbol normalization
        normalized = instance.normalize_symbol('BTC/USDT')
        assert normalized == 'BTC-USDT'

    def test_generated_feed_subscription_management(self):
        """Test generated feed subscription management."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.defines import TRADES

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        instance = feed_class(symbols=['BTC-USDT'], channels=[TRADES])

        # Should manage subscriptions
        assert 'BTC-USDT' in [str(s) for s in instance.normalized_symbols]
        assert TRADES in instance.subscription

    def test_generated_feed_callback_integration(self):
        """Test generated feed callback integration."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.defines import TRADES

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        callback_called = False
        def trade_callback(trade):
            nonlocal callback_called
            callback_called = True

        instance = feed_class(
            symbols=['BTC-USDT'],
            channels=[TRADES],
            callbacks={TRADES: trade_callback}
        )

        # Should have callback registered (callbacks are stored as lists)
        assert trade_callback in instance.callbacks[TRADES]


class TestBuilderConfigurationOptions:
    """Test builder configuration and customization options."""

    def test_builder_with_transport_config(self):
        """Test builder with transport configuration."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.exchanges.ccxt_config import CcxtExchangeConfig

        config = CcxtExchangeConfig(exchange_id='binance')

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class(
            exchange_id='binance',
            config=config
        )

        instance = feed_class()
        assert instance.ccxt_config == config

    def test_builder_with_adapter_overrides(self):
        """Test builder with adapter overrides."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.exchanges.ccxt_adapters import CcxtTradeAdapter

        class CustomTradeAdapter(CcxtTradeAdapter):
            def convert_trade(self, raw_trade):
                return super().convert_trade(raw_trade)

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class(
            exchange_id='binance',
            trade_adapter_class=CustomTradeAdapter
        )

        instance = feed_class()
        assert isinstance(instance.trade_adapter, CustomTradeAdapter)

    def test_builder_error_handling(self):
        """Test builder error handling for invalid exchanges."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder, UnsupportedExchangeError

        builder = CcxtExchangeBuilder()

        # Should raise appropriate errors
        with pytest.raises(UnsupportedExchangeError):
            builder.create_feed_class('nonexistent_exchange')


class TestFactoryIntegration:
    """Test integration with existing cryptofeed architecture."""

    def test_feedhandler_integration(self):
        """Test FeedHandler integration with generated feed classes."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.feedhandler import FeedHandler
        from cryptofeed.defines import TRADES

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        # Should integrate with FeedHandler
        fh = FeedHandler()

        feed_instance = feed_class(
            symbols=['BTC-USDT'],
            channels=[TRADES]
        )

        fh.add_feed(feed_instance)
        assert len(fh.feeds) == 1

    def test_backend_integration(self):
        """Test backend integration with generated feed classes."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder
        from cryptofeed.defines import TRADES

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        # Should support backend configuration
        instance = feed_class(
            symbols=['BTC-USDT'],
            channels=[TRADES],
            callbacks={TRADES: 'redis://localhost:6379'}  # Backend string
        )

        # Should parse backend configuration
        assert hasattr(instance, 'callbacks')

    def test_metrics_integration(self):
        """Test metrics integration with generated feed classes."""
        from cryptofeed.exchanges.ccxt_generic import CcxtExchangeBuilder

        builder = CcxtExchangeBuilder()
        feed_class = builder.create_feed_class('binance')

        instance = feed_class()

        # Should have basic feed capabilities that can be extended with metrics
        assert hasattr(instance, 'callbacks')
        assert hasattr(instance, 'subscription')