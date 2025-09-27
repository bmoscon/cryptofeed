"""CCXT exchange abstraction package."""

from .config import (
    CcxtProxyConfig,
    CcxtOptionsConfig,
    CcxtTransportConfig,
    CcxtExchangeConfig,
    CcxtConfig,
    CcxtExchangeContext,
    CcxtConfigExtensions,
    load_ccxt_config,
    validate_ccxt_config,
)
from .adapters import (
    CcxtTypeAdapter,
    CcxtTradeAdapter,
    CcxtOrderBookAdapter,
    AdapterRegistry,
    AdapterValidationError,
)
from .transport import CcxtRestTransport, CcxtWsTransport
from .generic import (
    CcxtMetadataCache,
    CcxtGenericFeed,
    OrderBookSnapshot,
    TradeUpdate,
    CcxtUnavailable,
)
from .builder import (
    CcxtExchangeBuilder,
    UnsupportedExchangeError,
    get_supported_ccxt_exchanges,
    get_exchange_builder,
    create_ccxt_feed,
)
from .feed import CcxtFeed

__all__ = [
    'CcxtProxyConfig',
    'CcxtOptionsConfig',
    'CcxtTransportConfig',
    'CcxtExchangeConfig',
    'CcxtConfig',
    'CcxtExchangeContext',
    'CcxtConfigExtensions',
    'load_ccxt_config',
    'validate_ccxt_config',
    'CcxtTypeAdapter',
    'CcxtTradeAdapter',
    'CcxtOrderBookAdapter',
    'AdapterRegistry',
    'AdapterValidationError',
    'CcxtRestTransport',
    'CcxtWsTransport',
    'CcxtMetadataCache',
    'CcxtGenericFeed',
    'OrderBookSnapshot',
    'TradeUpdate',
    'CcxtUnavailable',
    'CcxtExchangeBuilder',
    'UnsupportedExchangeError',
    'get_supported_ccxt_exchanges',
    'get_exchange_builder',
    'create_ccxt_feed',
    'CcxtFeed',
]
