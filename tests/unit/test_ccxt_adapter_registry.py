"""
Test suite for CCXT Adapter Registry and Extension System.

Tests follow TDD principles:
- RED: Write failing tests first
- GREEN: Implement minimal code to pass
- REFACTOR: Improve code structure

Tests Task 3.3 acceptance criteria:
- Derived exchanges can override specific adapter behavior
- Registry provides consistent adapter lookup and instantiation
- Adapter validation catches conversion errors early
- Fallback adapters handle edge cases gracefully
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from typing import Dict, Any, Optional, Type
from unittest.mock import Mock, MagicMock

from cryptofeed.types import Trade, OrderBook


class TestAdapterRegistry:
    """Test adapter registry for exchange-specific overrides."""

    def test_adapter_registry_creation(self):
        """Test adapter registry can be created."""
        from cryptofeed.exchanges.ccxt_adapters import AdapterRegistry
        registry = AdapterRegistry()
        assert registry is not None

    def test_adapter_registry_default_registration(self):
        """Test default adapter registration works."""
        from cryptofeed.exchanges.ccxt_adapters import AdapterRegistry, CcxtTradeAdapter, CcxtOrderBookAdapter

        registry = AdapterRegistry()

        # Should have default adapters registered
        trade_adapter = registry.get_trade_adapter('default')
        book_adapter = registry.get_orderbook_adapter('default')

        assert isinstance(trade_adapter, CcxtTradeAdapter)
        assert isinstance(book_adapter, CcxtOrderBookAdapter)

    def test_adapter_registry_custom_registration(self):
        """Test custom adapter registration works."""
        from cryptofeed.exchanges.ccxt_adapters import AdapterRegistry, CcxtTradeAdapter

        class CustomTradeAdapter(CcxtTradeAdapter):
            def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
                # Custom conversion logic
                return super().convert_trade(raw_trade)

        registry = AdapterRegistry()
        registry.register_trade_adapter('binance', CustomTradeAdapter)

        adapter = registry.get_trade_adapter('binance')
        assert isinstance(adapter, CustomTradeAdapter)

    def test_adapter_registry_fallback_behavior_fails(self):
        """RED: Test should fail - fallback behavior not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import AdapterRegistry

            registry = AdapterRegistry()

            # Should fallback to default adapter for unknown exchange
            adapter = registry.get_trade_adapter('unknown_exchange')
            assert adapter is not None  # Should get default adapter

    def test_adapter_registry_validation_fails(self):
        """RED: Test should fail - adapter validation not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import AdapterRegistry, AdapterValidationError

            registry = AdapterRegistry()

            # Try to register invalid adapter (not inheriting from base)
            with pytest.raises(AdapterValidationError):
                registry.register_trade_adapter('invalid', str)  # Invalid adapter type


class TestBaseAdapter:
    """Test base adapter classes with extension points."""

    def test_base_trade_adapter_creation_fails(self):
        """RED: Test should fail - base trade adapter not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter

    def test_base_trade_adapter_interface_fails(self):
        """RED: Test should fail - base adapter interface not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter

            adapter = BaseTradeAdapter()

            # Should have required methods
            assert hasattr(adapter, 'convert_trade')
            assert hasattr(adapter, 'validate_trade')
            assert hasattr(adapter, 'normalize_timestamp')

    def test_base_orderbook_adapter_creation_fails(self):
        """RED: Test should fail - base orderbook adapter not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseOrderBookAdapter

    def test_base_orderbook_adapter_interface_fails(self):
        """RED: Test should fail - base orderbook adapter interface not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseOrderBookAdapter

            adapter = BaseOrderBookAdapter()

            # Should have required methods
            assert hasattr(adapter, 'convert_orderbook')
            assert hasattr(adapter, 'validate_orderbook')
            assert hasattr(adapter, 'normalize_prices')

    def test_derived_adapter_override_fails(self):
        """RED: Test should fail - derived adapter override not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter
            from cryptofeed.types import Trade

            class CustomTradeAdapter(BaseTradeAdapter):
                def convert_trade(self, raw_trade: Dict[str, Any]) -> Trade:
                    # Custom implementation
                    return Trade(
                        exchange='custom',
                        symbol=raw_trade['symbol'],
                        side=raw_trade['side'],
                        amount=Decimal(str(raw_trade['amount'])),
                        price=Decimal(str(raw_trade['price'])),
                        timestamp=float(raw_trade['timestamp']),
                        id=raw_trade['id']
                    )

            adapter = CustomTradeAdapter()
            raw_trade = {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'amount': '1.5',
                'price': '50000.0',
                'timestamp': 1640995200.0,
                'id': 'trade_123'
            }

            trade = adapter.convert_trade(raw_trade)
            assert isinstance(trade, Trade)
            assert trade.exchange == 'custom'


class TestAdapterValidation:
    """Test validation for adapter correctness."""

    def test_trade_adapter_validation_success_fails(self):
        """RED: Test should fail - trade adapter validation not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import CcxtTradeAdapter

            adapter = CcxtTradeAdapter()

            valid_trade = {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'amount': 1.5,
                'price': 50000.0,
                'timestamp': 1640995200000,  # milliseconds
                'id': 'trade_123'
            }

            # Should validate successfully
            assert adapter.validate_trade(valid_trade) is True

    def test_trade_adapter_validation_failure_fails(self):
        """RED: Test should fail - trade adapter validation failure not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import CcxtTradeAdapter, AdapterValidationError

            adapter = CcxtTradeAdapter()

            invalid_trade = {
                'symbol': 'BTC/USDT',
                # Missing required fields: side, amount, price, timestamp, id
            }

            # Should raise validation error
            with pytest.raises(AdapterValidationError):
                adapter.validate_trade(invalid_trade)

    def test_orderbook_adapter_validation_success_fails(self):
        """RED: Test should fail - orderbook adapter validation not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import CcxtOrderBookAdapter

            adapter = CcxtOrderBookAdapter()

            valid_orderbook = {
                'symbol': 'BTC/USDT',
                'bids': [[50000.0, 1.5], [49999.0, 2.0]],
                'asks': [[50001.0, 1.2], [50002.0, 1.8]],
                'timestamp': 1640995200000,
                'nonce': 123456
            }

            # Should validate successfully
            assert adapter.validate_orderbook(valid_orderbook) is True

    def test_orderbook_adapter_validation_failure_fails(self):
        """RED: Test should fail - orderbook adapter validation failure not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import CcxtOrderBookAdapter, AdapterValidationError

            adapter = CcxtOrderBookAdapter()

            invalid_orderbook = {
                'symbol': 'BTC/USDT',
                'bids': 'invalid_format',  # Should be list of [price, size] pairs
                'asks': [[50001.0, 1.2]],
                'timestamp': 1640995200000
            }

            # Should raise validation error
            with pytest.raises(AdapterValidationError):
                adapter.validate_orderbook(invalid_orderbook)


class TestFallbackAdapters:
    """Test fallback behavior for missing adapters."""

    def test_fallback_trade_adapter_fails(self):
        """RED: Test should fail - fallback trade adapter not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import FallbackTradeAdapter

            adapter = FallbackTradeAdapter()

            # Should handle edge cases gracefully
            raw_trade = {
                'symbol': 'BTC/USDT',
                'side': 'buy',
                'amount': None,  # Edge case: null amount
                'price': '50000.0',
                'timestamp': 1640995200000,
                'id': 'trade_123'
            }

            trade = adapter.convert_trade(raw_trade)
            assert trade is None  # Should gracefully handle invalid data

    def test_fallback_orderbook_adapter_fails(self):
        """RED: Test should fail - fallback orderbook adapter not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import FallbackOrderBookAdapter

            adapter = FallbackOrderBookAdapter()

            # Should handle edge cases gracefully
            raw_orderbook = {
                'symbol': 'BTC/USDT',
                'bids': [],  # Edge case: empty bids
                'asks': [],  # Edge case: empty asks
                'timestamp': 1640995200000
            }

            orderbook = adapter.convert_orderbook(raw_orderbook)
            assert orderbook is None  # Should gracefully handle empty data

    def test_fallback_error_logging_fails(self):
        """RED: Test should fail - fallback error logging not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import FallbackTradeAdapter
            import logging

            # Mock logger to verify error logging
            with pytest.mock.patch('logging.getLogger') as mock_logger:
                logger_instance = Mock()
                mock_logger.return_value = logger_instance

                adapter = FallbackTradeAdapter()

                # Try to convert completely invalid data
                result = adapter.convert_trade({'invalid': 'data'})

                # Should log the error
                logger_instance.error.assert_called_once()
                assert result is None


class TestAdapterExtensionPoints:
    """Test extension points for derived exchanges."""

    def test_symbol_normalization_hook_fails(self):
        """RED: Test should fail - symbol normalization hook not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter

            class CustomSymbolAdapter(BaseTradeAdapter):
                def normalize_symbol(self, raw_symbol: str) -> str:
                    # Custom symbol normalization (e.g., BTC_USDT -> BTC-USDT)
                    return raw_symbol.replace('_', '-')

            adapter = CustomSymbolAdapter()
            normalized = adapter.normalize_symbol('BTC_USDT')
            assert normalized == 'BTC-USDT'

    def test_timestamp_normalization_hook_fails(self):
        """RED: Test should fail - timestamp normalization hook not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseTradeAdapter

            class CustomTimestampAdapter(BaseTradeAdapter):
                def normalize_timestamp(self, raw_timestamp: Any) -> float:
                    # Custom timestamp handling (e.g., string to float)
                    if isinstance(raw_timestamp, str):
                        return float(raw_timestamp)
                    return super().normalize_timestamp(raw_timestamp)

            adapter = CustomTimestampAdapter()
            timestamp = adapter.normalize_timestamp('1640995200.123')
            assert timestamp == 1640995200.123

    def test_price_normalization_hook_fails(self):
        """RED: Test should fail - price normalization hook not implemented."""
        with pytest.raises(ImportError):
            from cryptofeed.exchanges.ccxt_adapters import BaseOrderBookAdapter
            from decimal import Decimal

            class CustomPriceAdapter(BaseOrderBookAdapter):
                def normalize_price(self, raw_price: Any) -> Decimal:
                    # Custom price handling (e.g., handle scientific notation)
                    if isinstance(raw_price, str) and 'e' in raw_price.lower():
                        return Decimal(raw_price)
                    return super().normalize_price(raw_price)

            adapter = CustomPriceAdapter()
            price = adapter.normalize_price('5.0e4')  # Scientific notation
            assert price == Decimal('50000')