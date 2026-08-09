'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from datetime import datetime as dt, timezone
from typing import Dict, List, Union

from cryptofeed.defines import POSITIONS, TRANSACTIONS, BALANCES, ORDER_INFO, FILLS
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPSync, RestEndpoint
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol
from cryptofeed.config import Config


LOG = logging.getLogger(__name__)


class Exchange:
    id = NotImplemented
    websocket_endpoints = NotImplemented
    rest_endpoints = NotImplemented
    _parse_symbol_data = NotImplemented
    websocket_channels = NotImplemented
    request_limit = NotImplemented
    valid_candle_intervals = NotImplemented
    candle_interval_map = NotImplemented
    http_sync = HTTPSync()
    allow_empty_subscriptions = False

    def __init__(self, config=None, sandbox=False, subaccount=None, **kwargs):
        self.config = Config(config=config)
        self.sandbox = sandbox
        self.subaccount = subaccount

        keys = self.config[self.id.lower()] if self.subaccount is None else self.config[self.id.lower()][self.subaccount]
        self.key_id = keys.key_id
        self.key_secret = keys.key_secret
        self.key_passphrase = keys.key_passphrase
        self.account_name = keys.account_name

        self.ignore_invalid_instruments = self.config.ignore_invalid_instruments

        if not Symbols.populated(self.id):
            self.symbol_mapping()
        self.normalized_symbol_mapping, _ = Symbols.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

    @classmethod
    def timestamp_normalize(cls, ts: Union[str, dt]) -> float:
        if isinstance(ts, str):
            ts = dt.fromisoformat(ts)
        return ts.astimezone(timezone.utc).timestamp()

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for REST and Websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = {
            'rest': [],
            'websocket': list(cls.websocket_channels.keys())
        }
        return data

    @classmethod
    def symbols(cls, refresh=False) -> list:
        return list(cls.symbol_mapping(refresh=refresh).keys())

    @classmethod
    def _symbol_endpoint_prepare(cls, ep: RestEndpoint) -> Union[List[str], str]:
        """
        override if a specific exchange needs to do something first, like query an API
        to get a list of currencies, that are then used to build the list of symbol endpoints
        """
        return ep.route('instruments')

    @classmethod
    def symbol_mapping(cls, refresh=False, headers: dict = None) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            data = []
            for ep in cls.rest_endpoints:
                addr = cls._symbol_endpoint_prepare(ep)
                if isinstance(addr, list):
                    for ep in addr:
                        LOG.debug("%s: reading symbol information from %s", cls.id, ep)
                        data.append(cls.http_sync.read(ep, json=True, headers=headers, uuid=cls.id))
                else:
                    LOG.debug("%s: reading symbol information from %s", cls.id, addr)
                    data.append(cls.http_sync.read(addr, json=True, headers=headers, uuid=cls.id))

            syms, info = cls._parse_symbol_data(data if len(data) > 1 else data[0])
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

    @classmethod
    def std_channel_to_exchange(cls, channel: str) -> str:
        try:
            return cls.websocket_channels[channel]
        except KeyError:
            raise UnsupportedDataFeed(f'{channel} is not supported on {cls.id}')

    @classmethod
    def exchange_channel_to_std(cls, channel: str) -> str:
        for chan, exch in cls.websocket_channels.items():
            if exch == channel:
                return chan
        raise ValueError(f'Unable to normalize channel {cls.id}')

    @classmethod
    def is_authenticated_channel(cls, channel: str) -> bool:
        return channel in (ORDER_INFO, FILLS, TRANSACTIONS, BALANCES, POSITIONS)

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        try:
            return self.exchange_symbol_mapping[symbol]
        except KeyError:
            if self.ignore_invalid_instruments:
                LOG.warning('Invalid symbol %s configured for %s', symbol, self.id)
                return symbol
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    def std_symbol_to_exchange_symbol(self, symbol: Union[str, Symbol]) -> str:
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        try:
            return self.normalized_symbol_mapping[symbol]
        except KeyError:
            if self.ignore_invalid_instruments:
                LOG.warning('Invalid symbol %s configured for %s', symbol, self.id)
                return symbol
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

