"""CCXT exchange abstraction package."""

from .config import (
    CcxtProxyConfig,
    CcxtOptionsConfig,
    CcxtTransportConfig,
    CcxtExchangeConfig,
    CcxtConfig,
)
from .context import (
    CcxtExchangeContext,
    load_ccxt_config,
    validate_ccxt_config,
)
from .extensions import CcxtConfigExtensions
from .adapters import (
    AdapterHookRegistry,
    AdapterRegistry,
    AdapterValidationError,
    CcxtOrderBookAdapter,
    CcxtTradeAdapter,
    CcxtTypeAdapter,
    FallbackOrderBookAdapter,
    FallbackTradeAdapter,
    ccxt_orderbook_hook,
    ccxt_trade_hook,
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
from .exchanges import get_symbol_normalizer, load_exchange_overrides

load_exchange_overrides()

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
    'FallbackTradeAdapter',
    'FallbackOrderBookAdapter',
    'AdapterRegistry',
    'AdapterHookRegistry',
    'ccxt_trade_hook',
    'ccxt_orderbook_hook',
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
    'get_symbol_normalizer',
    'load_exchange_overrides',
]
