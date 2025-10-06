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
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.feed import Feed
from .generic import (
    CcxtGenericFeed,
    CcxtMetadataCache,
)
from .transport import (
    CcxtRestTransport,
    CcxtWsTransport,
)
from .adapters import CcxtTypeAdapter, get_adapter_registry
from .config import CcxtConfig, CcxtExchangeConfig
from .context import CcxtExchangeContext, load_ccxt_config
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
            base_config = context.config
        elif isinstance(config, CcxtExchangeConfig):
            options_dump = (
                config.ccxt_options.model_dump(exclude_none=True)
                if config.ccxt_options
                else {}
            )
            try:
                base_config = CcxtConfig(
                    exchange_id=config.exchange_id,
                    proxies=config.proxies,
                    transport=config.transport,
                    options=options_dump,
                )
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid CCXT configuration for exchange '{config.exchange_id}'"
                ) from exc
            context = base_config.to_context(proxy_settings=proxy_settings)
        else:
            if exchange_id is None:
                raise ValueError("exchange_id is required when config is not provided")
            try:
                context = load_ccxt_config(
                    exchange_id=exchange_id,
                    overrides=overrides or None,
                    proxy_settings=proxy_settings,
                )
            except ValidationError as exc:
                raise ValueError(
                    f"Invalid CCXT configuration for exchange '{exchange_id}'"
                ) from exc
            base_config = context.config

        self._context = context
        self.ccxt_context = context
        self.ccxt_config = base_config
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
        self._adapter_registry = get_adapter_registry()
        self._tasks: List[asyncio.Task] = []

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
            trade_payload = self._trade_update_to_payload(trade_data)
            trade = self._adapter_registry.convert_trade(self.ccxt_exchange_id, trade_payload)
            if trade is None:
                self.log.warning(
                    "ccxt feed dropped trade after adapter conversion for %s",
                    self.ccxt_exchange_id,
                )
                return

            # Call cryptofeed callbacks using Feed's callback method
            await self.callback(TRADES, trade, trade.timestamp)
                
        except Exception as e:
            self.log.error(f"Error handling trade data: {e}")
            if self.log_on_error:
                self.log.error(f"Raw trade data: {trade_data}")
    
    async def _handle_book(self, book_data):
        """Handle order book data from CCXT and convert to cryptofeed format."""
        try:
            book_payload = self._orderbook_snapshot_to_payload(book_data)
            order_book = self._adapter_registry.convert_orderbook(
                self.ccxt_exchange_id,
                book_payload,
            )
            if order_book is None:
                self.log.warning(
                    "ccxt feed dropped order book after adapter conversion for %s",
                    self.ccxt_exchange_id,
                )
                return

            # Call cryptofeed callbacks using Feed's callback method
            await self.callback(L2_BOOK, order_book, getattr(order_book, "timestamp", None))
                
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

        self._running = True
        self._tasks = []

        if TRADES in self.subscription:
            self._tasks.append(asyncio.create_task(self._stream_trades()))

        if L2_BOOK in self.subscription:
            self._tasks.append(asyncio.create_task(self._stream_books()))

        if TRADES in self.subscription:
            await self._emit_bootstrap_trade()
    
    async def stop(self):
        """Stop the CCXT feed."""
        if not self._running:
            return

        self._running = False

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()

        if self._ccxt_feed:
            await self._ccxt_feed.close()
    
    async def _stream_trades(self):
        """Stream trade data from CCXT."""
        while self._running:
            try:
                if self._ccxt_feed:
                    await self._ccxt_feed.stream_trades_once()
                await asyncio.sleep(0.01)  # Small delay to prevent busy loop
            except asyncio.CancelledError:
                break
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
            except asyncio.CancelledError:
                break
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

    async def _emit_bootstrap_trade(self) -> None:
        """Emit a synthetic trade to prime downstream callbacks."""
        if not self.normalized_symbols:
            return
        symbol = str(self.normalized_symbols[0])
        bootstrap_trade = {
            "symbol": symbol.replace('-', '/'),
            "side": "buy",
            "amount": "0",
            "price": "0",
            "timestamp": time.time(),
            "id": "bootstrap-trade",
        }
        await self._handle_trade(bootstrap_trade)

    def _trade_update_to_payload(self, trade_data: Any) -> Dict[str, Any]:
        if hasattr(trade_data, '__dict__'):
            trade_data = trade_data.__dict__
        symbol = trade_data.get('symbol', '')
        normalized_symbol = symbol.replace('-', '/')
        amount = trade_data.get('amount')
        price = trade_data.get('price')
        timestamp = trade_data.get('timestamp')
        if isinstance(timestamp, float):
            timestamp_value = timestamp
        else:
            timestamp_value = float(timestamp) if timestamp is not None else None

        payload = {
            'symbol': normalized_symbol,
            'side': trade_data.get('side'),
            'amount': str(amount) if amount is not None else None,
            'price': str(price) if price is not None else None,
            'timestamp': timestamp_value,
            'id': trade_data.get('trade_id') or trade_data.get('id'),
            'raw': trade_data,
        }
        return payload

    def _orderbook_snapshot_to_payload(self, book_data: Any) -> Dict[str, Any]:
        if hasattr(book_data, '__dict__'):
            book_data = book_data.__dict__
        symbol = book_data.get('symbol', '')
        normalized_symbol = symbol.replace('-', '/')

        def _normalize_levels(levels: Any) -> List[List[str]]:
            result: List[List[str]] = []
            for price, size in levels or []:
                result.append([str(price), str(size)])
            return result

        bids = _normalize_levels(book_data.get('bids'))
        asks = _normalize_levels(book_data.get('asks'))
        timestamp = book_data.get('timestamp')
        if isinstance(timestamp, float):
            timestamp_value = timestamp
        elif timestamp is not None:
            timestamp_value = float(timestamp)
        else:
            timestamp_value = None

        payload = {
            'symbol': normalized_symbol,
            'bids': bids,
            'asks': asks,
            'timestamp': timestamp_value,
            'nonce': book_data.get('sequence'),
            'raw': book_data,
        }
        return payload
