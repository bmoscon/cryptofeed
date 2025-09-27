"""
CCXT Feed integration with cryptofeed architecture.

Follows engineering principles from CLAUDE.md:
- SOLID: Inherits from Feed, single responsibility
- KISS: Simple bridge between CCXT and cryptofeed
- DRY: Reuses existing Feed infrastructure
- NO LEGACY: Modern async patterns only
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.feed import Feed
from cryptofeed.exchanges.ccxt_generic import (
    CcxtGenericFeed,
    CcxtMetadataCache,
    CcxtRestTransport,
    CcxtWsTransport,
)
from cryptofeed.exchanges.ccxt_adapters import CcxtTypeAdapter
from cryptofeed.exchanges.ccxt_config import (
    CcxtConfig,
    CcxtExchangeConfig,
    CcxtExchangeContext,
    load_ccxt_config,
)
from cryptofeed.proxy import get_proxy_injector
from cryptofeed.symbols import Symbol, Symbols, str_to_symbol


class CcxtFeed(Feed):
    """
    CCXT-based feed that integrates with cryptofeed architecture.
    
    Bridges CCXT exchanges into the standard cryptofeed Feed inheritance hierarchy,
    allowing seamless integration with existing callbacks, backends, and tooling.
    """
    
    # Required Exchange attributes (will be set dynamically)
    id = NotImplemented
    rest_endpoints = []  # CCXT handles endpoints internally
    websocket_endpoints = []  # CCXT handles endpoints internally  
    websocket_channels = {
        L2_BOOK: 'depth',
        TRADES: 'trades'
    }
    
    def __init__(
        self,
        exchange_id: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None,
        ccxt_options: Optional[Dict[str, any]] = None,
        config: Optional[CcxtExchangeConfig] = None,
        **kwargs
    ):
        """
        Initialize CCXT feed with standard cryptofeed Feed integration.

        Args:
            exchange_id: CCXT exchange identifier (e.g., 'backpack')
            proxies: Proxy configuration for REST/WebSocket (legacy dict format)
            ccxt_options: Additional CCXT client options (legacy dict format)
            config: Complete typed configuration (preferred over individual args)
            **kwargs: Standard Feed arguments (symbols, channels, callbacks, etc.)
        """
        transport_keys = {'snapshot_interval', 'websocket_enabled', 'rest_only', 'use_market_id'}
        transport_overrides: Dict[str, Any] = {}
        for key in list(kwargs.keys()):
            if key in transport_keys:
                transport_overrides[key] = kwargs.pop(key)

        credential_keys = {
            'api_key',
            'secret',
            'passphrase',
            'sandbox',
            'rate_limit',
            'enable_rate_limit',
            'timeout',
        }
        overrides: Dict[str, Any] = {}
        if proxies:
            overrides['proxies'] = proxies
        if ccxt_options:
            overrides['options'] = ccxt_options
        if transport_overrides:
            overrides['transport'] = transport_overrides
        for field in list(kwargs.keys()):
            if field in credential_keys:
                overrides[field] = kwargs.pop(field)

        proxy_settings = self._resolve_proxy_settings()

        if isinstance(config, CcxtExchangeContext):
            context = config
        elif isinstance(config, CcxtExchangeConfig):
            options_dump = (
                config.ccxt_options.model_dump(exclude_none=True)
                if config.ccxt_options
                else {}
            )
            base_config = CcxtConfig(
                exchange_id=config.exchange_id,
                proxies=config.proxies,
                transport=config.transport,
                options=options_dump,
            )
            context = base_config.to_context(proxy_settings=proxy_settings)
        else:
            if exchange_id is None:
                raise ValueError("exchange_id is required when config is not provided")
            context = load_ccxt_config(
                exchange_id=exchange_id,
                overrides=overrides or None,
                proxy_settings=proxy_settings,
            )

        self._context = context
        self.ccxt_exchange_id = context.exchange_id
        self.proxies: Dict[str, str] = {}
        if context.http_proxy_url:
            self.proxies['rest'] = context.http_proxy_url
        if context.websocket_proxy_url:
            self.proxies['websocket'] = context.websocket_proxy_url
        self.ccxt_options = dict(context.ccxt_options)

        self._metadata_cache = CcxtMetadataCache(self.ccxt_exchange_id, context=context)
        self._ccxt_feed: Optional[CcxtGenericFeed] = None
        self._running = False

        self.__class__.id = self._get_exchange_constant(self.ccxt_exchange_id)

        self._initialize_symbol_mapping()

        if 'symbols' in kwargs and kwargs['symbols']:
            kwargs['symbols'] = [
                str_to_symbol(sym) if isinstance(sym, str) else sym
                for sym in kwargs['symbols']
            ]

        exchange_constant = self._get_exchange_constant(self.ccxt_exchange_id).lower()
        if self.ccxt_options.get('apiKey') and self.ccxt_options.get('secret'):
            credentials_config = {
                exchange_constant: {
                    'key_id': self.ccxt_options.get('apiKey'),
                    'key_secret': self.ccxt_options.get('secret'),
                    'key_passphrase': self.ccxt_options.get('password'),
                    'account_name': None,
                }
            }
            kwargs.setdefault('config', credentials_config)

        kwargs.setdefault('sandbox', context.use_sandbox)

        super().__init__(**kwargs)

        self.key_id = self.ccxt_options.get('apiKey')
        self.key_secret = self.ccxt_options.get('secret')
        self.key_passphrase = self.ccxt_options.get('password')

        self.log = logging.getLogger('feedhandler')
        
    def _get_exchange_constant(self, exchange_id: str) -> str:
        """Map CCXT exchange ID to cryptofeed exchange constant."""
        # This mapping should be expanded as more exchanges are added
        mapping = {
            'backpack': 'BACKPACK',
            'binance': 'BINANCE',
            'coinbase': 'COINBASE',
            # Add more mappings as needed
        }
        return mapping.get(exchange_id, exchange_id.upper())
    
    def _initialize_symbol_mapping(self):
        """Initialize symbol mapping for this CCXT exchange."""
        # Create empty symbol mapping to satisfy parent requirements
        normalized_mapping = {}
        info = {'symbols': []}

        # Register with Symbols system
        if not Symbols.populated(self.__class__.id):
            Symbols.set(self.__class__.id, normalized_mapping, info)

    def _resolve_proxy_settings(self):
        injector = get_proxy_injector()
        if injector is None:
            return None
        return getattr(injector, 'settings', None)
    
    @classmethod 
    def symbol_mapping(cls, refresh=False, headers=None):
        """Override symbol mapping since CCXT handles this internally."""
        # Return empty mapping since CCXT manages symbols
        # This prevents the parent class from trying to fetch symbol data
        return {}
    
    def std_symbol_to_exchange_symbol(self, symbol):
        """Override to use CCXT symbol conversion."""
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        # For CCXT feeds, just return the symbol as-is since CCXT handles conversion
        return symbol
    
    def exchange_symbol_to_std_symbol(self, symbol):
        """Override to use CCXT symbol conversion."""
        # For CCXT feeds, just return the symbol as-is since CCXT handles conversion  
        return symbol
    
    async def _initialize_ccxt_feed(self):
        """Initialize the underlying CCXT feed components."""
        if self._ccxt_feed is not None:
            return
            
        # Ensure metadata cache is loaded
        await self._metadata_cache.ensure()
        
        # Convert symbols to CCXT format
        ccxt_symbols = [
            CcxtTypeAdapter.normalize_symbol_to_ccxt(str(symbol)) 
            for symbol in self.normalized_symbols
        ]
        
        # Get channels list
        channels = list(self.subscription.keys())
        
        # Create CCXT feed
        self._ccxt_feed = CcxtGenericFeed(
            exchange_id=self.ccxt_exchange_id,
            symbols=ccxt_symbols,
            channels=channels,
            metadata_cache=self._metadata_cache,
            snapshot_interval=self._context.transport.snapshot_interval,
            websocket_enabled=self._context.transport.websocket_enabled,
            rest_only=self._context.transport.rest_only,
            config_context=self._context,
        )
        
        # Register our callbacks with CCXT feed
        if TRADES in channels:
            self._ccxt_feed.register_callback(TRADES, self._handle_trade)
        if L2_BOOK in channels:
            self._ccxt_feed.register_callback(L2_BOOK, self._handle_book)
    
    async def _handle_trade(self, trade_data):
        """Handle trade data from CCXT and convert to cryptofeed format."""
        try:
            # Convert CCXT trade to cryptofeed Trade
            trade = CcxtTypeAdapter.to_cryptofeed_trade(
                trade_data.__dict__ if hasattr(trade_data, '__dict__') else trade_data,
                self.id
            )
            
            # Call cryptofeed callbacks using Feed's callback method
            await self.callback(TRADES, trade, trade.timestamp)
                
        except Exception as e:
            self.log.error(f"Error handling trade data: {e}")
            if self.log_on_error:
                self.log.error(f"Raw trade data: {trade_data}")
    
    async def _handle_book(self, book_data):
        """Handle order book data from CCXT and convert to cryptofeed format."""
        try:
            # Convert CCXT book to cryptofeed OrderBook
            book = CcxtTypeAdapter.to_cryptofeed_orderbook(
                book_data.__dict__ if hasattr(book_data, '__dict__') else book_data,
                self.id
            )
            
            # Call cryptofeed callbacks using Feed's callback method
            await self.callback(L2_BOOK, book, book.timestamp)
                
        except Exception as e:
            self.log.error(f"Error handling book data: {e}")
            if self.log_on_error:
                self.log.error(f"Raw book data: {book_data}")
    
    async def subscribe(self, connection: AsyncConnection):
        """
        Subscribe to channels (not used in CCXT integration).
        
        CCXT handles subscriptions internally, so this is a no-op
        that maintains compatibility with Feed interface.
        """
        pass
    
    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        """
        Handle WebSocket messages (not used in CCXT integration).
        
        CCXT handles message parsing internally, so this is a no-op
        that maintains compatibility with Feed interface.
        """
        pass
    
    async def start(self):
        """Start the CCXT feed."""
        if self._running:
            return
            
        await self._initialize_ccxt_feed()
        
        # Start processing data
        self._running = True
        
        # Start tasks for different data types
        tasks = []
        
        if TRADES in self.subscription:
            tasks.append(asyncio.create_task(self._stream_trades()))
            
        if L2_BOOK in self.subscription:
            tasks.append(asyncio.create_task(self._stream_books()))
        
        # Wait for all tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop(self):
        """Stop the CCXT feed."""
        self._running = False
        if self._ccxt_feed:
            # CCXT feed cleanup would go here
            pass
    
    async def _stream_trades(self):
        """Stream trade data from CCXT."""
        while self._running:
            try:
                if self._ccxt_feed:
                    await self._ccxt_feed.stream_trades_once()
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            except Exception as e:
                self.log.error(f"Error streaming trades: {e}")
                await asyncio.sleep(1)  # Longer delay on error
    
    async def _stream_books(self):
        """Stream order book data from CCXT.""" 
        while self._running:
            try:
                if self._ccxt_feed:
                    # Bootstrap L2 book periodically
                    await self._ccxt_feed.bootstrap_l2()
                await asyncio.sleep(30)  # Refresh every 30 seconds
            except Exception as e:
                self.log.error(f"Error streaming books: {e}")
                await asyncio.sleep(5)  # Delay on error
    
    async def _handle_test_trade_message(self):
        """Test method for callback integration tests."""
        # Create a test trade for testing purposes
        test_trade_data = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": "0.1", 
            "price": "30000",
            "timestamp": 1700000000000,
            "id": "test123"
        }
        await self._handle_trade(test_trade_data)
