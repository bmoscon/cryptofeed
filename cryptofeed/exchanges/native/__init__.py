"""Shared helpers for native (non-CCXT) exchange integrations."""

from .auth import Ed25519AuthHelper, Ed25519Credentials, NativeAuthError
from .rest import NativeOrderBookSnapshot, NativeRestClient, NativeRestError
from .router import NativeMessageRouter
from .symbols import NativeMarket, NativeSymbolService
from .ws import NativeWsSession, NativeSubscription, NativeWebsocketError
from .metrics import NativeExchangeMetrics
from .health import NativeHealthReport, evaluate_health

__all__ = [
    "Ed25519AuthHelper",
    "Ed25519Credentials",
    "NativeAuthError",
    "NativeOrderBookSnapshot",
    "NativeRestClient",
    "NativeRestError",
    "NativeWsSession",
    "NativeSubscription",
    "NativeWebsocketError",
    "NativeMessageRouter",
    "NativeMarket",
    "NativeSymbolService",
    "NativeExchangeMetrics",
    "NativeHealthReport",
    "evaluate_health",
]
