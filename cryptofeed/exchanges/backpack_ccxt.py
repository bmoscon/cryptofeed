"""Backpack-specific ccxt/ccxt.pro integration built on the generic adapter."""
from __future__ import annotations

from cryptofeed.exchanges.ccxt_generic import (
    CcxtGenericFeed,
    CcxtMetadataCache,
    CcxtRestTransport,
    CcxtWsTransport,
    CcxtUnavailable,
    OrderBookSnapshot,
    TradeUpdate,
)


class BackpackMetadataCache(CcxtMetadataCache):
    def __init__(self) -> None:
        super().__init__("backpack", use_market_id=True)


class BackpackRestTransport(CcxtRestTransport):
    pass


class BackpackWsTransport(CcxtWsTransport):
    pass


class CcxtBackpackFeed(CcxtGenericFeed):
    def __init__(
        self,
        *,
        symbols,
        channels,
        snapshot_interval: int = 30,
        websocket: bool = True,
        rest_only: bool = False,
        metadata_cache: BackpackMetadataCache | None = None,
        rest_transport_factory=BackpackRestTransport,
        ws_transport_factory=BackpackWsTransport,
    ) -> None:
        super().__init__(
            exchange_id="backpack",
            symbols=symbols,
            channels=channels,
            snapshot_interval=snapshot_interval,
            websocket_enabled=websocket,
            rest_only=rest_only,
            metadata_cache=metadata_cache or BackpackMetadataCache(),
            rest_transport_factory=rest_transport_factory,
            ws_transport_factory=ws_transport_factory,
        )


__all__ = [
    "CcxtUnavailable",
    "BackpackMetadataCache",
    "BackpackRestTransport",
    "BackpackWsTransport",
    "CcxtBackpackFeed",
    "OrderBookSnapshot",
    "TradeUpdate",
]
