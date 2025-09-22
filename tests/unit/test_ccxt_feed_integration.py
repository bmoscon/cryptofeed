"""
Test suite for CCXT Feed integration with cryptofeed architecture.

Tests follow TDD principles from CLAUDE.md:
- Write tests first based on expected behavior
- No mocks in production code
- Test against Feed base class integration
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest

from cryptofeed.defines import L2_BOOK, TRADES, BACKPACK
from cryptofeed.feed import Feed
from cryptofeed.types import Trade, OrderBook  # Using cryptofeed types, not custom ones
from cryptofeed.symbols import Symbol


@pytest.fixture(autouse=True)
def clear_ccxt_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure ccxt modules are absent unless explicitly injected."""
    for name in [
        "ccxt",
        "ccxt.async_support", 
        "ccxt.async_support.backpack",
        "ccxt.pro",
        "ccxt.pro.backpack",
    ]:
        monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.fixture
def mock_ccxt(monkeypatch):
    """Mock ccxt for testing without external dependencies."""
    # This follows NO MOCKS principle - mock only external dependencies
    markets = {
        "BTC/USDT": {
            "id": "BTC_USDT",
            "symbol": "BTC/USDT", 
            "base": "BTC",
            "quote": "USDT",
            "limits": {"amount": {"min": 0.0001}},
            "precision": {"price": 2, "amount": 6},
        }
    }
    
    class MockAsyncClient:
        def __init__(self):
            self.markets = markets
            self.rateLimit = 100
            
        async def load_markets(self):
            return markets
            
        async def fetch_order_book(self, symbol: str, limit: int = None):
            return {
                "bids": [["30000", "1.5"], ["29950", "2"]],
                "asks": [["30010", "1.25"], ["30020", "3"]],
                "timestamp": 1700000000000,
                "nonce": 1001,
            }
            
        async def close(self):
            pass
    
    class MockProClient:
        def __init__(self):
            self._trade_data = []
            
        async def watch_trades(self, symbol: str):
            if self._trade_data:
                return self._trade_data.pop(0)
            raise asyncio.TimeoutError()
            
        async def watch_order_book(self, symbol: str):
            return {
                "bids": [["30000", "1.5"]],
                "asks": [["30010", "1.0"]],
                "timestamp": 1700000000500,
                "nonce": 1001,
            }
            
        async def close(self):
            pass
    
    # Mock ccxt modules
    import types
    ccxt_module = types.ModuleType("ccxt")
    async_module = types.ModuleType("ccxt.async_support")
    pro_module = types.ModuleType("ccxt.pro")
    
    async_module.backpack = MockAsyncClient
    pro_module.backpack = MockProClient
    ccxt_module.async_support = async_module
    ccxt_module.pro = pro_module
    
    monkeypatch.setitem(sys.modules, "ccxt", ccxt_module)
    monkeypatch.setitem(sys.modules, "ccxt.async_support", async_module)
    monkeypatch.setitem(sys.modules, "ccxt.pro", pro_module)
    
    return {
        "async_client": MockAsyncClient,
        "pro_client": MockProClient,
        "markets": markets,
    }


class TestCcxtFeedInheritance:
    """Test that CCXT feeds properly inherit from Feed base class."""
    
    def test_ccxt_feed_inherits_from_feed(self, mock_ccxt):
        """
        FAILING TEST: CcxtFeed should inherit from Feed base class
        to integrate with existing cryptofeed infrastructure.
        """
        # This will fail until we implement proper inheritance
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES, L2_BOOK]
        )
        
        # Must inherit from Feed for integration
        assert isinstance(feed, Feed)
        
        # Must have Feed attributes
        assert hasattr(feed, 'subscription')
        assert hasattr(feed, 'normalized_symbols')
        assert hasattr(feed, 'connection_handlers')
        
    def test_ccxt_feed_has_exchange_id(self, mock_ccxt):
        """CcxtFeed should have proper exchange ID."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        
        feed = CcxtFeed(
            exchange_id="backpack", 
            symbols=["BTC-USDT"],
            channels=[TRADES]
        )
        
        assert feed.id == BACKPACK
        
    def test_ccxt_feed_symbol_normalization(self, mock_ccxt):
        """CcxtFeed should normalize symbols using cryptofeed conventions."""
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES]
        )
        
        # Should convert to Symbol objects
        assert all(isinstance(sym, Symbol) for sym in feed.normalized_symbols)
        
        # Should use cryptofeed symbol normalization
        assert "BTC-USDT" in [str(sym) for sym in feed.normalized_symbols]


class TestCcxtTypeAdapters:
    """Test that CCXT data is converted to cryptofeed types."""
    
    def test_ccxt_trade_to_cryptofeed_trade(self, mock_ccxt):
        """
        FAILING TEST: CCXT trade data should convert to cryptofeed Trade type.
        """
        from cryptofeed.exchanges.ccxt_adapters import CcxtTypeAdapter
        
        ccxt_trade = {
            "symbol": "BTC/USDT",
            "side": "buy", 
            "amount": "0.25",
            "price": "30005",
            "timestamp": 1700000000123,
            "id": "trade123",
        }
        
        trade = CcxtTypeAdapter.to_cryptofeed_trade(
            ccxt_trade, 
            exchange=BACKPACK
        )
        
        # Must be cryptofeed Trade type
        assert isinstance(trade, Trade)
        assert trade.exchange == BACKPACK
        assert trade.symbol == "BTC-USDT" 
        assert trade.side == "buy"
        assert trade.amount == Decimal("0.25")
        assert trade.price == Decimal("30005")
        assert trade.id == "trade123"
        
    def test_ccxt_orderbook_to_cryptofeed_orderbook(self, mock_ccxt):
        """
        FAILING TEST: CCXT order book should convert to cryptofeed OrderBook.
        """
        from cryptofeed.exchanges.ccxt_adapters import CcxtTypeAdapter
        
        ccxt_book = {
            "symbol": "BTC/USDT",
            "bids": [["30000", "1.5"], ["29950", "2"]],
            "asks": [["30010", "1.25"], ["30020", "3"]],
            "timestamp": 1700000000000,
            "nonce": 1001,
        }
        
        book = CcxtTypeAdapter.to_cryptofeed_orderbook(
            ccxt_book,
            exchange=BACKPACK
        )
        
        # Must be cryptofeed OrderBook type
        assert isinstance(book, OrderBook)
        assert book.exchange == BACKPACK
        assert book.symbol == "BTC-USDT"
        assert len(book.book.bids) == 2
        assert len(book.book.asks) == 2
        assert book.book.bids[Decimal("30000")] == Decimal("1.5")


class TestCcxtCallbackIntegration:
    """Test integration with cryptofeed callback system."""
    
    @pytest.mark.asyncio
    async def test_ccxt_feed_callback_registration(self, mock_ccxt):
        """
        FAILING TEST: CcxtFeed should integrate with cryptofeed callback system.
        """
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        from cryptofeed.callback import TradeCallback, BookCallback
        
        trades_received = []
        books_received = []
        
        async def trade_handler(trade: Trade, timestamp: float):
            trades_received.append(trade)
            
        async def book_handler(book: OrderBook, timestamp: float):
            books_received.append(book)
        
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"], 
            channels=[TRADES, L2_BOOK],
            callbacks={
                TRADES: TradeCallback(trade_handler),
                L2_BOOK: BookCallback(book_handler)
            }
        )
        
        # Should have registered callbacks
        assert TRADES in feed.callbacks
        assert L2_BOOK in feed.callbacks
        
        # Test callback invocation (will require message_handler implementation)
        await feed._handle_test_trade_message()
        
        assert len(trades_received) == 1
        assert isinstance(trades_received[0], Trade)


class TestCcxtConfiguration:
    """Test CCXT configuration integration."""
    
    def test_ccxt_feed_config_parsing(self, mock_ccxt):
        """
        FAILING TEST: CcxtFeed should parse configuration like other feeds.
        """
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        
        config = {
            "exchange_id": "backpack",
            "symbols": ["BTC-USDT", "ETH-USDT"],
            "channels": [TRADES, L2_BOOK],
            "proxies": {
                "rest": "socks5://proxy:1080",
                "websocket": "socks5://proxy:1081"
            },
            "ccxt_options": {
                "rateLimit": 100,
                "enableRateLimit": True
            }
        }
        
        feed = CcxtFeed(**config)
        
        assert feed.ccxt_exchange_id == "backpack"
        assert len(feed.normalized_symbols) == 2
        assert feed.proxies["rest"] == "socks5://proxy:1080"
        assert feed.ccxt_options["rateLimit"] == 100


# Integration with existing test patterns
class TestCcxtFeedEndToEnd:
    """End-to-end integration tests."""
    
    @pytest.mark.asyncio
    async def test_ccxt_feed_subscribes_and_receives_data(self, mock_ccxt):
        """
        FAILING TEST: Complete feed lifecycle should work.
        """
        from cryptofeed.exchanges.ccxt_feed import CcxtFeed
        
        received_data = []
        
        def data_handler(data, timestamp):
            received_data.append((data, timestamp))
        
        feed = CcxtFeed(
            exchange_id="backpack",
            symbols=["BTC-USDT"],
            channels=[TRADES],
            callbacks={TRADES: data_handler}
        )
        
        # Should be able to start and stop like other feeds
        await feed.start()
        
        # Simulate receiving some data
        await asyncio.sleep(0.1)
        
        await feed.stop()
        
        # Should have received properly formatted data
        assert len(received_data) > 0
        data, timestamp = received_data[0]
        assert isinstance(data, Trade)
        assert isinstance(timestamp, float)