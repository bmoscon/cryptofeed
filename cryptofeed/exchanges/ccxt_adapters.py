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
    
    @staticmethod 
    def normalize_symbol_from_ccxt(symbol: str) -> str:
        """
        Convert CCXT symbol format to cryptofeed format.
        
        Args:
            symbol: CCXT symbol (BTC/USDT)
            
        Returns:
            Cryptofeed symbol format (BTC-USDT)
        """
        return symbol.replace("/", "-")