'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from datetime import datetime as dt, timezone
from typing import Dict, Optional, Tuple, Union

from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, L3_BOOK, OPEN_INTEREST, TICKER, TRADES, TRANSACTIONS, BALANCES, ORDER_INFO, FILLS
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
    valid_candle_intervals = NotImplemented
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
        return channel in (ORDER_INFO, FILLS, TRANSACTIONS, BALANCES)

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

    def _datetime_normalize(self, timestamp: Union[str, int, float, dt]) -> float:
        if isinstance(timestamp, (float, int)):
            return timestamp
        if isinstance(timestamp, dt):
            return timestamp.replace(tzinfo=timezone.utc).timestamp()
        if isinstance(timestamp, str):
            try:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()

    def _interval_normalize(self, start, end) -> Tuple[Optional[float], Optional[float]]:
        if start:
            start = self._datetime_normalize(start)
            if not end:
                end = dt.now()
        if end:
            end = self._datetime_normalize(end)
        return start, end if start else None

    # public / non account specific
    def ticker_sync(self, symbol: str, retry_count=1, retry_delay=60):
        return asyncio.get_event_loop().run_until_complete(self.ticker(symbol, retry_count=retry_count, retry_delay=retry_delay))

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def candles_sync(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        gen = self.candles(symbol, start=start, end=end, interval=interval, retry_count=retry_count, retry_delay=retry_delay)
        try:
            loop = asyncio.get_event_loop()

            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            return

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        raise NotImplementedError

    def trades_sync(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        gen = self.trades(symbol, start=start, end=end, retry_count=retry_count, retry_delay=retry_delay)
        try:
            loop = asyncio.get_event_loop()

            while True:
                yield loop.run_until_complete(gen.__anext__())
        except StopAsyncIteration:
            return

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def funding_sync(self, symbol: str, retry_count=1, retry_delay=60):
        return asyncio.get_event_loop().run_until_complete(self.funding(symbol, retry_count=retry_count, retry_delay=retry_delay))

    async def funding(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def open_interest_sync(self, symbol: str, retry_count=1, retry_delay=60):
        return asyncio.get_event_loop().run_until_complete(self.open_interest(symbol, retry_count=retry_count, retry_delay=retry_delay))

    async def open_interest(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l2_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        return asyncio.get_event_loop().run_until_complete(self.l2_book(symbol, retry_count=retry_count, retry_delay=retry_delay))

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l3_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        return asyncio.get_event_loop().run_until_complete(self.l3_book(symbol, retry_count=retry_count, retry_delay=retry_delay))

    async def l3_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    # account specific
    def place_order_sync(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        return asyncio.get_event_loop().run_until_complete(self.place_order(symbol, side, order_type, amount, price, **kwargs))

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        raise NotImplementedError

    def cancel_order_sync(self, order_id: str, **kwargs):
        return asyncio.get_event_loop().run_until_complete(self.cancel_order(order_id, **kwargs))

    async def cancel_order(self, order_id: str, **kwargs):
        raise NotImplementedError

    def orders_sync(self, symbol: str = None):
        return asyncio.get_event_loop().run_until_complete(self.orders(symbol))

    async def orders(self, symbol: str = None):
        raise NotImplementedError

    def order_status_sync(self, order_id: str):
        return asyncio.get_event_loop().run_until_complete(self.order_status(order_id))

    async def order_status(self, order_id: str):
        raise NotImplementedError

    def trade_history_sync(self, symbol: str = None, start=None, end=None):
        return asyncio.get_event_loop().run_until_complete(self.trade_history(symbol, start, end))

    async def trade_history(self, symbol: str = None, start=None, end=None):
        raise NotImplementedError

    def balances_sync(self):
        return asyncio.get_event_loop().run_until_complete(self.balances())

    async def balances(self):
        raise NotImplementedError

    def positions_sync(self, **kwargs):
        return asyncio.get_event_loop().run_until_complete(self.positions(**kwargs))

    async def positions(self, **kwargs):
        raise NotImplementedError

    def ledger_sync(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        return asyncio.get_event_loop().run_until_complete(self.ledger(aclass, asset, ledger_type, start, end))

    async def ledger(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        raise NotImplementedError

    def __getitem__(self, key):
        if key == TRADES:
            return self.trades
        elif key == CANDLES:
            return self.candles
        elif key == FUNDING:
            return self.funding
        elif key == L2_BOOK:
            return self.l2_book
        elif key == L3_BOOK:
            return self.l3_book
        elif key == TICKER:
            return self.ticker
        elif key == OPEN_INTEREST:
            return self.open_interest
