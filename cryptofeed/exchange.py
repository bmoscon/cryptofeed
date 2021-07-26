'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.log import get_logger
from cryptofeed.config import Config
from decimal import Decimal
import logging
from typing import Any, Dict, Union

from cryptofeed.defines import ACC_TRANSACTIONS, BALANCES, ORDER_INFO, USER_FILLS
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPSync
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol


LOG = logging.getLogger('feedhandler')


class Exchange:
    id = NotImplemented
    symbol_endpoint = NotImplemented
    _parse_symbol_data = NotImplemented
    websocket_channels = NotImplemented
    rest_channels = NotImplemented
    rest_options = NotImplemented
    http_sync = HTTPSync()

    def __init__(self, *args, config=None, sandbox=False, subaccount=None, **kwargs):
        self.config = Config(config=config)
        self.sandbox = sandbox

        keys = self.config[self.id.lower()] if subaccount is None else self.config[self.id.lower()][subaccount]
        self.key_id = keys.key_id
        self.key_secret = keys.key_secret
        self.key_passphrase = keys.key_passphrase
        self.account_name = keys.account_name

        if not Symbols.populated(self.id):
            self.symbol_mapping()
        self.normalized_symbol_mapping, _= Symbols.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

    @classmethod
    def timestamp_normalize(ts: Any):
        raise NotImplementedError

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for REST and Websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = {
            'rest': list(cls.rest_channels),
            'websocket': list(cls.websocket_channels.keys())
        }
        return data

    @classmethod
    def symbols(cls, refresh=False) -> Dict:
        return cls.symbol_mapping(refresh=refresh)

    @classmethod
    def symbol_mapping(cls, refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            if isinstance(cls.symbol_endpoint, list):
                data = []
                for ep in cls.symbol_endpoint:
                    data.append(cls.http_sync.read(ep, json=True, uuid=cls.id))
            elif isinstance(cls.symbol_endpoint, dict):
                data = []
                for input, output in cls.symbol_endpoint.items():
                    for d in cls.http_sync.read(input, json=True, uuid=cls.id):
                        data.append(cls.http_sync.read(f"{output}{d}", json=True, uuid=cls.id))
            else:
                data = cls.http_sync.read(cls.symbol_endpoint, json=True, uuid=cls.id)

            syms, info = cls._parse_symbol_data(data)
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
    def is_authenticated_channel(channel: str) -> bool:
        return channel in (ORDER_INFO, USER_FILLS, ACC_TRANSACTIONS, BALANCES)

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        try:
            return self.exchange_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    def std_symbol_to_exchange_symbol(self, symbol: Union[str, Symbol]) -> str:
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        try:
            return self.normalized_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    # Definitions for REST interface
    def _handle_error(self, resp):
        if resp.status_code != 200:
            self.log.error("%s: Status code %d for URL %s", self.id, resp.status_code, resp.url)
            self.log.error("%s: Headers: %s", self.id, resp.headers)
            self.log.error("%s: Resp: %s", self.id, resp.text)
            resp.raise_for_status()

    # public / non account specific
    def ticker(self, symbol: str, retry=None, retry_wait=10):
        raise NotImplementedError

    def trades(self, symbol: str, start=None, end=None, retry=None, retry_wait=0):
        raise NotImplementedError

    def funding(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    def l2_book(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    def l3_book(self, symbol: str, retry=None, retry_wait=0):
        raise NotImplementedError

    # account specific
    def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        raise NotImplementedError

    def cancel_order(self, order_id: str):
        raise NotImplementedError

    def orders(self, sumbol: str = None):
        """
        Return outstanding orders
        """
        raise NotImplementedError

    def order_status(self, order_id: str):
        """
        Look up status of an order by id
        """
        raise NotImplementedError

    def trade_history(self, symbol: str = None, start=None, end=None):
        """
        Executed trade history
        """
        raise NotImplementedError

    def balances(self):
        raise NotImplementedError

    def positions(self, **kwargs):
        raise NotImplementedError

    def ledger(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        """
        Executed trade history
        """
        raise NotImplementedError

    def __getitem__(self, key):
        if key == 'trades':
            return self.trades
        elif key == 'funding':
            return self.funding
        elif key == 'l2_book':
            return self.l2_book
        elif key == 'l3_book':
            return self.l3_book
        elif key == 'ticker':
            return self.ticker
