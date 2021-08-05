'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
from datetime import datetime as dt, timezone
from typing import Dict, Union

from cryptofeed.defines import FUNDING, L2_BOOK, L3_BOOK, TICKER, TRADES, TRANSACTIONS, BALANCES, ORDER_INFO, USER_FILLS
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPSync
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol, UnsupportedTradingOption
from cryptofeed.config import Config


LOG = logging.getLogger('feedhandler')


class Exchange:
    id = NotImplemented
    symbol_endpoint = NotImplemented
    _parse_symbol_data = NotImplemented
    websocket_channels = NotImplemented
    request_limit = NotImplemented
    http_sync = HTTPSync()

    def __init__(self, config=None, sandbox=False, subaccount=None, **kwargs):
        self.config = Config(config=config)
        self.sandbox = sandbox
        self.subaccount = subaccount

        keys = self.config[self.id.lower()] if self.subaccount is None else self.config[self.id.lower()][self.subaccount]
        self.key_id = keys.key_id
        self.key_secret = keys.key_secret
        self.key_passphrase = keys.key_passphrase
        self.account_name = keys.account_name

        if not Symbols.populated(self.id):
            self.symbol_mapping()
        self.normalized_symbol_mapping, _ = Symbols.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

    @classmethod
    def timestamp_normalize(cls, ts: dt) -> float:
        return ts.timestamp()

    @classmethod
    def normalize_order_options(cls, option: str):
        if option not in cls.order_options:
            raise UnsupportedTradingOption
        return cls.order_options[option]

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for REST and Websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = {
            'rest': list(cls.rest_channels) if hasattr(cls, 'rest_channels') else [],
            'websocket': list(cls.websocket_channels.keys())
        }
        return data

    @classmethod
    def symbols(cls, refresh=False) -> Dict:
        return list(cls.symbol_mapping(refresh=refresh).keys())

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
    def is_authenticated_channel(cls, channel: str) -> bool:
        return channel in (ORDER_INFO, USER_FILLS, TRANSACTIONS, BALANCES)

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


class RestExchange:
    api = NotImplemented
    sandbox_api = NotImplemented
    rest_channels = NotImplemented
    order_options = NotImplemented

    def _datetime_normalize(self, timestamp: Union[str, float, dt]):
        if isinstance(timestamp, float):
            return timestamp
        if isinstance(timestamp, dt):
            return timestamp.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(timestamp, str):
            try:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()

    def _handle_error(self, resp):
        if resp.status_code != 200:
            LOG.error("%s: Status code %d for URL %s", self.id, resp.status_code, resp.url)
            LOG.error("%s: Headers: %s", self.id, resp.headers)
            LOG.error("%s: Resp: %s", self.id, resp.text)
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
        if key == TRADES:
            return self.trades
        elif key == FUNDING:
            return self.funding
        elif key == L2_BOOK:
            return self.l2_book
        elif key == L3_BOOK:
            return self.l3_book
        elif key == TICKER:
            return self.ticker
