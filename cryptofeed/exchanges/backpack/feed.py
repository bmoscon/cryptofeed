"""Native Backpack feed integrating configuration, transports, and adapters."""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BACKPACK, L2_BOOK, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol, Symbols

from .adapters import BackpackOrderBookAdapter, BackpackTradeAdapter
from .auth import BackpackAuthHelper
from .config import BackpackConfig
from .rest import BackpackRestClient
from .router import BackpackMessageRouter
from .symbols import BackpackSymbolService
from .ws import BackpackSubscription, BackpackWsSession


LOG = logging.getLogger("feedhandler")


class BackpackFeed(Feed):
    """Backpack exchange feed built on native cryptofeed abstractions."""

    id = BACKPACK
    rest_endpoints: List = []
    websocket_endpoints: List = []
    websocket_channels = {
        TRADES: "trades",
        L2_BOOK: "l2",
    }

    def __init__(
        self,
        *,
        config: Optional[BackpackConfig] = None,
        feature_flag_enabled: bool = True,
        rest_client_factory=None,
        ws_session_factory=None,
        symbol_service: Optional[BackpackSymbolService] = None,
        **kwargs,
    ) -> None:
        if not feature_flag_enabled:
            raise RuntimeError("Native Backpack feed is disabled. Set feature_flag_enabled=True to opt-in.")

        self.config = config or BackpackConfig()
        Symbols.set(self.id, {}, {})
        self._rest_client_factory = rest_client_factory or (lambda cfg: BackpackRestClient(cfg))
        self._ws_session_factory = ws_session_factory or (lambda cfg: BackpackWsSession(cfg))
        self._rest_client = self._rest_client_factory(self.config)
        self._symbol_service = symbol_service or BackpackSymbolService(rest_client=self._rest_client)
        self._trade_adapter = BackpackTradeAdapter(exchange=self.id)
        self._order_book_adapter = BackpackOrderBookAdapter(exchange=self.id, max_depth=kwargs.get("max_depth", 0))
        self._router: Optional[BackpackMessageRouter] = None
        self._ws_session: Optional[BackpackWsSession] = None

        super().__init__(**kwargs)

    # ------------------------------------------------------------------
    # Symbol handling
    # ------------------------------------------------------------------
    def std_symbol_to_exchange_symbol(self, symbol):
        if isinstance(symbol, Symbol):
            normalized = symbol.normalized
        else:
            normalized = str(symbol)

        try:
            return self._symbol_service.native_symbol(normalized)
        except KeyError:
            return normalized.replace("-", "_")

    def exchange_symbol_to_std_symbol(self, symbol):
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        return symbol.replace("_", "-")

    # ------------------------------------------------------------------
    # Feed lifecycle helpers
    # ------------------------------------------------------------------
    async def _initialize_router(self) -> None:
        if self._router is None:
            self._router = BackpackMessageRouter(
                trade_adapter=self._trade_adapter,
                order_book_adapter=self._order_book_adapter,
                trade_callback=self._callback(TRADES),
                order_book_callback=self._callback(L2_BOOK),
            )

    def _callback(self, channel):
        callbacks = self.callbacks.get(channel)
        if not callbacks:
            return None

        async def handler(message, timestamp):
            for cb in callbacks:
                await cb(message, timestamp)

        return handler

    async def _ensure_symbol_metadata(self) -> None:
        await self._symbol_service.ensure()

    def _build_ws_session(self) -> BackpackWsSession:
        auth_helper = BackpackAuthHelper(self.config) if self.config.requires_auth else None
        session = self._ws_session_factory(self.config)
        if auth_helper and getattr(session, "_auth_helper", None) is None:
            session._auth_helper = auth_helper
        return session

    async def subscribe(self, connection: AsyncConnection):
        # Overridden to integrate Backpack subscriptions with WS session
        await self._ensure_symbol_metadata()
        await self._initialize_router()

        if not self._ws_session:
            self._ws_session = self._build_ws_session()
            await self._ws_session.open()

        subscriptions = []
        for std_channel, exchange_channel in self.websocket_channels.items():
            if exchange_channel not in self.subscription:
                continue
            symbols = [self.exchange_symbol_to_std_symbol(sym) for sym in self.subscription[exchange_channel]]
            subscriptions.append(
                BackpackSubscription(
                    channel=exchange_channel,
                    symbols=symbols,
                    private=self.is_authenticated_channel(std_channel),
                )
            )

        if subscriptions:
            await self._ws_session.subscribe(subscriptions)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        if self._router:
            await self._router.dispatch(msg)

    async def shutdown(self) -> None:
        if self._ws_session:
            await self._ws_session.close()
        await self._rest_client.close()

    # ------------------------------------------------------------------
    # Override connect to use Backpack session
    # ------------------------------------------------------------------
    def connect(self) -> List[Tuple[AsyncConnection, callable, callable]]:
        # Defer websocket handling to BackpackWsSession managed in subscribe
        LOG.debug("BackpackFeed connect invoked - relying on custom BackpackWsSession")
        return []
