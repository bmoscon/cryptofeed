"""
Type adapters for converting between CCXT and cryptofeed data types.

Follows engineering principles from CLAUDE.md:
- SOLID: Single responsibility for type conversion
- DRY: Reusable conversion logic
- NO MOCKS: Uses real type definitions
- CONSISTENT NAMING: Clear adapter pattern
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from cryptofeed.types import Trade, OrderBook
from order_book import OrderBook as _OrderBook
from cryptofeed.defines import BID, ASK


class CcxtTypeAdapter:
    """Adapter to convert between CCXT and cryptofeed data types."""
    
    @staticmethod
    def to_cryptofeed_trade(ccxt_trade: Dict[str, Any], exchange: str) -> Trade:
        """
        Convert CCXT trade format to cryptofeed Trade.
        
        Args:
            ccxt_trade: CCXT trade dictionary
            exchange: Exchange identifier
            
        Returns:
            cryptofeed Trade object
        """
        # Normalize symbol from CCXT format (BTC/USDT) to cryptofeed format (BTC-USDT)
        symbol = ccxt_trade["symbol"].replace("/", "-")
        
        # Convert timestamp from milliseconds to seconds
        timestamp = float(ccxt_trade["timestamp"]) / 1000.0
        
        return Trade(
            exchange=exchange,
            symbol=symbol,
            side=ccxt_trade["side"],
            amount=Decimal(str(ccxt_trade["amount"])),
            price=Decimal(str(ccxt_trade["price"])),
            timestamp=timestamp,
            id=ccxt_trade["id"],
            raw=ccxt_trade
        )
    
    @staticmethod
    def to_cryptofeed_orderbook(ccxt_book: Dict[str, Any], exchange: str) -> OrderBook:
        """
        Convert CCXT order book format to cryptofeed OrderBook.
        
        Args:
            ccxt_book: CCXT order book dictionary
            exchange: Exchange identifier
            
        Returns:
            cryptofeed OrderBook object
        """
        # Normalize symbol from CCXT format (BTC/USDT) to cryptofeed format (BTC-USDT)
        symbol = ccxt_book["symbol"].replace("/", "-")
        
        # Convert timestamp from milliseconds to seconds
        timestamp = float(ccxt_book["timestamp"]) / 1000.0 if ccxt_book.get("timestamp") else None
        
        # Process bids (buy orders) - convert to dict
        bids = {}
        for price_str, amount_str in ccxt_book["bids"]:
            price = Decimal(str(price_str))
            amount = Decimal(str(amount_str))
            bids[price] = amount
        
        # Process asks (sell orders) - convert to dict
        asks = {}
        for price_str, amount_str in ccxt_book["asks"]:
            price = Decimal(str(price_str))
            amount = Decimal(str(amount_str))
            asks[price] = amount
        
        # Create OrderBook using the correct constructor
        order_book = OrderBook(
            exchange=exchange,
            symbol=symbol,
            bids=bids,
            asks=asks
        )
        
        # Set additional attributes
        order_book.timestamp = timestamp
        order_book.raw = ccxt_book
        
        return order_book
    
    @staticmethod
    def normalize_symbol_to_ccxt(symbol: str) -> str:
        """
        Convert cryptofeed symbol format to CCXT format.
        
        Args:
            symbol: Cryptofeed symbol (BTC-USDT)
            
        Returns:
            CCXT symbol format (BTC/USDT)
        """
        return symbol.replace("-", "/")


# =============================================================================
# Adapter Registry and Extension System (Task 3.3)
# =============================================================================

import logging
from abc import ABC, abstractmethod
from typing import Type, Optional, Union


LOG = logging.getLogger('feedhandler')


class AdapterValidationError(Exception):
    """Raised when adapter validation fails."""
    pass


class BaseTradeAdapter(ABC):
    """Base adapter for trade conversion with extension points."""

    @abstractmethod
    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        """Convert raw trade data to cryptofeed Trade object."""
        pass

    def validate_trade(self, raw_trade: Dict[str, Any]) -> bool:
        """Validate raw trade data structure."""
        required_fields = ['symbol', 'side', 'amount', 'price', 'timestamp', 'id']
        for field in required_fields:
            if field not in raw_trade:
                raise AdapterValidationError(f"Missing required field: {field}")
        return True

    def normalize_timestamp(self, raw_timestamp: Any) -> float:
        """Normalize timestamp to float seconds."""
        if isinstance(raw_timestamp, (int, float)):
            # Assume milliseconds if > 1e10, else seconds
            if raw_timestamp > 1e10:
                return float(raw_timestamp) / 1000.0
            return float(raw_timestamp)
        elif isinstance(raw_timestamp, str):
            return float(raw_timestamp)
        else:
            raise AdapterValidationError(f"Invalid timestamp format: {raw_timestamp}")

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Normalize symbol format. Override in derived classes."""
        return raw_symbol.replace("/", "-")


class BaseOrderBookAdapter(ABC):
    """Base adapter for order book conversion with extension points."""

    @abstractmethod
    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        """Convert raw order book data to cryptofeed OrderBook object."""
        pass

    def validate_orderbook(self, raw_orderbook: Dict[str, Any]) -> bool:
        """Validate raw order book data structure."""
        required_fields = ['symbol', 'bids', 'asks', 'timestamp']
        for field in required_fields:
            if field not in raw_orderbook:
                raise AdapterValidationError(f"Missing required field: {field}")

        # Validate bids/asks format
        if not isinstance(raw_orderbook['bids'], list):
            raise AdapterValidationError("Bids must be a list")
        if not isinstance(raw_orderbook['asks'], list):
            raise AdapterValidationError("Asks must be a list")

        return True

    def normalize_prices(self, price_levels: list) -> Dict[Decimal, Decimal]:
        """Normalize price levels to Decimal format."""
        result = {}
        for price, size in price_levels:
            result[Decimal(str(price))] = Decimal(str(size))
        return result

    def normalize_price(self, raw_price: Any) -> Decimal:
        """Normalize price to Decimal. Override in derived classes."""
        return Decimal(str(raw_price))


class CcxtTradeAdapter(BaseTradeAdapter):
    """CCXT implementation of trade adapter."""

    def __init__(self, exchange: str = "ccxt"):
        self.exchange = exchange

    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        """Convert CCXT trade to cryptofeed Trade."""
        try:
            self.validate_trade(raw_trade)

            return Trade(
                exchange=self.exchange,
                symbol=self.normalize_symbol(raw_trade["symbol"]),
                side=raw_trade["side"],
                amount=Decimal(str(raw_trade["amount"])),
                price=Decimal(str(raw_trade["price"])),
                timestamp=self.normalize_timestamp(raw_trade["timestamp"]),
                id=raw_trade["id"],
                raw=raw_trade
            )
        except (AdapterValidationError, Exception) as e:
            LOG.error(f"Failed to convert trade: {e}")
            return None


class CcxtOrderBookAdapter(BaseOrderBookAdapter):
    """CCXT implementation of order book adapter."""

    def __init__(self, exchange: str = "ccxt"):
        self.exchange = exchange

    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        """Convert CCXT order book to cryptofeed OrderBook."""
        try:
            self.validate_orderbook(raw_orderbook)

            symbol = self.normalize_symbol(raw_orderbook["symbol"])
            timestamp = self.normalize_timestamp(raw_orderbook["timestamp"]) if raw_orderbook.get("timestamp") else None

            # Process bids and asks
            bids = self.normalize_prices(raw_orderbook["bids"])
            asks = self.normalize_prices(raw_orderbook["asks"])

            order_book = OrderBook(
                exchange=self.exchange,
                symbol=symbol,
                bids=bids,
                asks=asks
            )

            order_book.timestamp = timestamp
            order_book.raw = raw_orderbook
            sequence = (
                raw_orderbook.get('nonce')
                or raw_orderbook.get('sequence')
                or raw_orderbook.get('seq')
            )
            if sequence is not None:
                try:
                    order_book.sequence_number = int(sequence)
                except (TypeError, ValueError):
                    order_book.sequence_number = sequence

            return order_book
        except (AdapterValidationError, Exception) as e:
            LOG.error(f"Failed to convert order book: {e}")
            return None

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Convert CCXT symbol (BTC/USDT) to cryptofeed format (BTC-USDT)."""
        return raw_symbol.replace("/", "-")

    def normalize_timestamp(self, raw_timestamp: Any) -> float:
        """Convert timestamp to float seconds."""
        if isinstance(raw_timestamp, (int, float)):
            # CCXT typically uses milliseconds
            if raw_timestamp > 1e10:
                return float(raw_timestamp) / 1000.0
            return float(raw_timestamp)
        if isinstance(raw_timestamp, str):
            return float(raw_timestamp)
        raise AdapterValidationError(f"Invalid timestamp format: {raw_timestamp}")


class FallbackTradeAdapter(BaseTradeAdapter):
    """Fallback adapter that handles edge cases gracefully."""

    def convert_trade(self, raw_trade: Dict[str, Any]) -> Optional[Trade]:
        """Convert trade with graceful error handling."""
        try:
            # Check for minimum required fields
            if not all(field in raw_trade for field in ['symbol', 'side']):
                LOG.error(f"Missing critical fields in trade: {raw_trade}")
                return None

            # Handle missing or null values
            amount = raw_trade.get('amount')
            price = raw_trade.get('price')
            timestamp = raw_trade.get('timestamp')
            trade_id = raw_trade.get('id', 'unknown')

            if amount is None or price is None:
                LOG.error(f"Invalid amount/price in trade: {raw_trade}")
                return None

            return Trade(
                exchange="fallback",
                symbol=self.normalize_symbol(raw_trade["symbol"]),
                side=raw_trade["side"],
                amount=Decimal(str(amount)),
                price=Decimal(str(price)),
                timestamp=self.normalize_timestamp(timestamp) if timestamp else 0.0,
                id=str(trade_id),
                raw=raw_trade
            )
        except Exception as e:
            LOG.error(f"Fallback trade adapter failed: {e}")
            return None


class FallbackOrderBookAdapter(BaseOrderBookAdapter):
    """Fallback adapter for order book that handles edge cases gracefully."""

    def convert_orderbook(self, raw_orderbook: Dict[str, Any]) -> Optional[OrderBook]:
        """Convert order book with graceful error handling."""
        try:
            # Check for minimum required fields
            symbol = raw_orderbook.get('symbol')
            if not symbol:
                LOG.error(f"Missing symbol in order book: {raw_orderbook}")
                return None

            bids = raw_orderbook.get('bids', [])
            asks = raw_orderbook.get('asks', [])

            # Handle empty order book
            if not bids and not asks:
                LOG.warning(f"Empty order book for {symbol}")
                return None

            # Process with error handling
            bid_dict = {}
            ask_dict = {}

            for price, size in bids:
                try:
                    bid_dict[Decimal(str(price))] = Decimal(str(size))
                except (ValueError, TypeError):
                    continue

            for price, size in asks:
                try:
                    ask_dict[Decimal(str(price))] = Decimal(str(size))
                except (ValueError, TypeError):
                    continue

            order_book = OrderBook(
                exchange="fallback",
                symbol=self.normalize_symbol(symbol),
                bids=bid_dict,
                asks=ask_dict
            )

            timestamp = raw_orderbook.get('timestamp')
            if timestamp:
                order_book.timestamp = self.normalize_timestamp(timestamp)

            order_book.raw = raw_orderbook
            return order_book

        except Exception as e:
            LOG.error(f"Fallback order book adapter failed: {e}")
            return None

    def normalize_symbol(self, raw_symbol: str) -> str:
        """Convert symbol with error handling."""
        try:
            return raw_symbol.replace("/", "-")
        except (AttributeError, TypeError):
            return str(raw_symbol)


class AdapterRegistry:
    """Registry for managing exchange-specific adapters."""

    def __init__(self):
        self._trade_adapters: Dict[str, Type[BaseTradeAdapter]] = {}
        self._orderbook_adapters: Dict[str, Type[BaseOrderBookAdapter]] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register default adapters."""
        self._trade_adapters['default'] = CcxtTradeAdapter
        self._orderbook_adapters['default'] = CcxtOrderBookAdapter

    def register_trade_adapter(self, exchange_id: str, adapter_class: Type[BaseTradeAdapter]):
        """Register a trade adapter for a specific exchange."""
        if not issubclass(adapter_class, BaseTradeAdapter):
            raise AdapterValidationError(f"Adapter must inherit from BaseTradeAdapter: {adapter_class}")

        self._trade_adapters[exchange_id] = adapter_class
        LOG.info(f"Registered trade adapter for {exchange_id}: {adapter_class.__name__}")

    def register_orderbook_adapter(self, exchange_id: str, adapter_class: Type[BaseOrderBookAdapter]):
        """Register an order book adapter for a specific exchange."""
        if not issubclass(adapter_class, BaseOrderBookAdapter):
            raise AdapterValidationError(f"Adapter must inherit from BaseOrderBookAdapter: {adapter_class}")

        self._orderbook_adapters[exchange_id] = adapter_class
        LOG.info(f"Registered order book adapter for {exchange_id}: {adapter_class.__name__}")

    def get_trade_adapter(self, exchange_id: str) -> BaseTradeAdapter:
        """Get trade adapter instance for exchange (with fallback to default)."""
        adapter_class = self._trade_adapters.get(exchange_id, self._trade_adapters['default'])
        return adapter_class(exchange=exchange_id)

    def get_orderbook_adapter(self, exchange_id: str) -> BaseOrderBookAdapter:
        """Get order book adapter instance for exchange (with fallback to default)."""
        adapter_class = self._orderbook_adapters.get(exchange_id, self._orderbook_adapters['default'])
        return adapter_class(exchange=exchange_id)

    def list_registered_adapters(self) -> Dict[str, Dict[str, str]]:
        """List all registered adapters."""
        return {
            'trade_adapters': {k: v.__name__ for k, v in self._trade_adapters.items()},
            'orderbook_adapters': {k: v.__name__ for k, v in self._orderbook_adapters.items()}
        }


# Global registry instance
_adapter_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    """Get the global adapter registry instance."""
    return _adapter_registry


# Update __all__ to include new classes
__all__ = [
    'CcxtTypeAdapter',
    'AdapterRegistry',
    'BaseTradeAdapter',
    'BaseOrderBookAdapter',
    'CcxtTradeAdapter',
    'CcxtOrderBookAdapter',
    'FallbackTradeAdapter',
    'FallbackOrderBookAdapter',
    'AdapterValidationError',
    'get_adapter_registry'
]
