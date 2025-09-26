"""Backpack native exchange integration scaffolding."""
from __future__ import annotations

from .config import BackpackConfig, BackpackAuthSettings
from .auth import BackpackAuthHelper, BackpackAuthError
from .symbols import BackpackSymbolService, BackpackMarket
from .rest import BackpackRestClient, BackpackOrderBookSnapshot, BackpackRestError
from .ws import BackpackWsSession, BackpackSubscription, BackpackWebsocketError
from .metrics import BackpackMetrics
from .health import BackpackHealthReport, evaluate_health
from .feed import BackpackFeed

__all__ = [
    "BackpackConfig",
    "BackpackAuthSettings",
    "BackpackAuthHelper",
    "BackpackAuthError",
    "BackpackSymbolService",
    "BackpackMarket",
    "BackpackRestClient",
    "BackpackOrderBookSnapshot",
    "BackpackRestError",
    "BackpackWsSession",
    "BackpackSubscription",
    "BackpackWebsocketError",
    "BackpackMetrics",
    "BackpackHealthReport",
    "evaluate_health",
    "BackpackFeed",
]
