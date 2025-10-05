"""Builder utilities for dynamically generating CCXT feed classes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Type

from cryptofeed.feed import Feed

from .adapters import BaseOrderBookAdapter, BaseTradeAdapter
from .feed import CcxtFeed
from .generic import CcxtMetadataCache, CcxtUnavailable
from .generic import get_supported_ccxt_exchanges as _get_supported_ccxt_exchanges
from .config import CcxtExchangeConfig


class UnsupportedExchangeError(Exception):
    """Raised when an unsupported exchange is requested."""


class CcxtExchangeBuilder:
    """Factory for creating CCXT-based feed classes."""

    def __init__(self):
        self._supported_exchanges: Optional[Set[str]] = None

    def _get_supported_exchanges(self) -> Set[str]:
        if self._supported_exchanges is None:
            self._supported_exchanges = set(_get_supported_ccxt_exchanges())
        return self._supported_exchanges

    def validate_exchange_id(self, exchange_id: str) -> bool:
        return self.normalize_exchange_id(exchange_id) in self._get_supported_exchanges()

    @staticmethod
    def normalize_exchange_id(exchange_id: str) -> str:
        normalized = exchange_id.lower()
        mappings = {
            'coinbase-pro': 'coinbasepro',
            'huobi_pro': 'huobipro',
            'huobi-pro': 'huobipro',
            'binance_us': 'binanceus',
            'binance-us': 'binanceus',
        }
        return mappings.get(normalized, normalized.replace('-', '').replace('_', ''))

    def create_feed_class(
        self,
        exchange_id: str,
        *,
        symbol_normalizer: Optional[callable] = None,
        subscription_filter: Optional[callable] = None,
        endpoint_overrides: Optional[Dict[str, str]] = None,
        config: Optional[CcxtExchangeConfig] = None,
        trade_adapter_class: Optional[Type[BaseTradeAdapter]] = None,
        orderbook_adapter_class: Optional[Type[BaseOrderBookAdapter]] = None,
    ) -> Type[Feed]:
        normalized_id = self.normalize_exchange_id(exchange_id)
        if not self.validate_exchange_id(exchange_id):
            raise UnsupportedExchangeError(f"Exchange '{exchange_id}' is not supported by CCXT")

        class_name = f"{exchange_id.title().replace('-', '').replace('_', '')}CcxtFeed"

        class_dict: Dict[str, Any] = {
            'exchange': normalized_id,
            'id': normalized_id.upper(),
            '_original_exchange_id': exchange_id,
            '_symbol_normalizer': symbol_normalizer,
            '_subscription_filter': subscription_filter,
            '_endpoint_overrides': endpoint_overrides or {},
            '_config': config,
        }

        if symbol_normalizer:
            def normalize_symbol(self, symbol: str) -> str:
                return symbol_normalizer(symbol)
            class_dict['normalize_symbol'] = normalize_symbol
        else:
            def _default_symbol_normalizer(symbol: str) -> str:
                normalized = symbol.replace('/', '-').replace(':', '-')
                if normalized_id == 'hyperliquid':
                    if symbol.endswith('-PERP') or normalized.endswith('-PERP'):
                        return normalized.replace(':', '-')
                    base_quote = symbol.split(':')[0]
                    if '/' in base_quote:
                        base, quote = base_quote.split('/')
                    else:
                        parts = normalized.split('-')
                        base = parts[0]
                        quote = parts[1] if len(parts) > 1 else parts[0]
                    return f"{base}-{quote}-PERP"
                return normalized

            class_dict['normalize_symbol'] = lambda self, symbol: _default_symbol_normalizer(symbol)

        if subscription_filter:
            def should_subscribe(self, symbol: str, channel: str) -> bool:
                return subscription_filter(symbol, channel)
            class_dict['should_subscribe'] = should_subscribe

        if endpoint_overrides:
            if 'rest' in endpoint_overrides:
                class_dict['rest_endpoint'] = endpoint_overrides['rest']
            if 'websocket' in endpoint_overrides:
                class_dict['ws_endpoint'] = endpoint_overrides['websocket']

        if trade_adapter_class:
            class_dict['trade_adapter_class'] = trade_adapter_class
            class_dict['trade_adapter'] = property(lambda self: self.trade_adapter_class(exchange=self.exchange))

        if orderbook_adapter_class:
            class_dict['orderbook_adapter_class'] = orderbook_adapter_class
            class_dict['orderbook_adapter'] = property(lambda self: self.orderbook_adapter_class(exchange=self.exchange))

        def __init__(self, *args, **kwargs):
            if self._config:
                kwargs['config'] = self._config
                self.config = self._config
            else:
                kwargs['exchange_id'] = normalized_id
            super(generated_class, self).__init__(*args, **kwargs)

        class_dict['__init__'] = __init__

        generated_class = type(class_name, (CcxtFeed,), class_dict)
        return generated_class


_exchange_builder = CcxtExchangeBuilder()


def get_supported_ccxt_exchanges() -> List[str]:
    return _get_supported_ccxt_exchanges()


def get_exchange_builder() -> CcxtExchangeBuilder:
    return _exchange_builder


def create_ccxt_feed(exchange_id: str, **kwargs) -> Type[Feed]:
    return _exchange_builder.create_feed_class(exchange_id, **kwargs)


__all__ = [
    'CcxtExchangeBuilder',
    'UnsupportedExchangeError',
    'get_supported_ccxt_exchanges',
    'get_exchange_builder',
    'create_ccxt_feed',
]
