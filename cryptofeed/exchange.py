'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from datetime import datetime as dt, timezone
from typing import AsyncGenerator, Dict, List, Optional, Tuple, Union

from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, L3_BOOK, OPEN_INTEREST, POSITIONS, TICKER, TRADES, TRANSACTIONS, BALANCES, ORDER_INFO, FILLS
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPSync, RestEndpoint
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol, UnsupportedTradingOption
from cryptofeed.config import Config


LOG = logging.getLogger('feedhandler')


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
    def timestamp_normalize(cls, ts: dt) -> float:
        return ts.astimezone(timezone.utc).timestamp()

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


class RestExchange:
    api = NotImplemented
    sandbox_api = NotImplemented
    rest_channels = NotImplemented
    order_options = NotImplemented

    def _sync_run_coroutine(self, coroutine):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coroutine)

    def _sync_run_generator(self, generator: AsyncGenerator):
        loop = asyncio.get_event_loop()

        try:
            while True:
                yield loop.run_until_complete(generator.__anext__())
        except StopAsyncIteration:
            return

    def _datetime_normalize(self, timestamp: Union[str, int, float, dt]) -> float:
        if isinstance(timestamp, (float, int)):
            return timestamp
        if isinstance(timestamp, dt):
            return timestamp.astimezone(timezone.utc).timestamp()

        if isinstance(timestamp, str):
            try:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return dt.strptime(timestamp, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()

    def _interval_normalize(self, start, end) -> Tuple[Optional[float], Optional[float]]:
        if start:
            start = self._datetime_normalize(start)
            if not end:
                end = dt.utcnow()
        if end:
            end = self._datetime_normalize(end)
        if start and start > end:
            raise ValueError('Start time must be less than or equal to end time')
        return start, end if start else None

    # public / non account specific
    def ticker_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.ticker(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def candles_sync(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        gen = self.candles(symbol, start=start, end=end, interval=interval, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_generator(gen)

    async def candles(self, symbol: str, start=None, end=None, interval='1m', retry_count=1, retry_delay=60):
        raise NotImplementedError

    def trades_sync(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        gen = self.trades(symbol, start=start, end=end, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_generator(gen)

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def funding_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.funding(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def funding(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def open_interest_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.open_interest(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def open_interest(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l2_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.l2_book(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    def l3_book_sync(self, symbol: str, retry_count=1, retry_delay=60):
        co = self.l3_book(symbol, retry_count=retry_count, retry_delay=retry_delay)
        return self._sync_run_coroutine(co)

    async def l3_book(self, symbol: str, retry_count=1, retry_delay=60):
        raise NotImplementedError

    # account specific
    def place_order_sync(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        co = self.place_order(symbol, side, order_type, amount, price, **kwargs)
        return self._sync_run_coroutine(co)

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, **kwargs):
        raise NotImplementedError

    def cancel_order_sync(self, order_id: str, **kwargs):
        co = self.cancel_order(order_id, **kwargs)
        return self._sync_run_coroutine(co)

    async def cancel_order(self, order_id: str, **kwargs):
        raise NotImplementedError

    def orders_sync(self, symbol: str = None):
        co = self.orders(symbol)
        return self._sync_run_coroutine(co)

    async def orders(self, symbol: str = None):
        raise NotImplementedError

    def order_status_sync(self, order_id: str):
        co = self.order_status(order_id)
        return self._sync_run_coroutine(co)

    async def order_status(self, order_id: str):
        raise NotImplementedError

    def trade_history_sync(self, symbol: str = None, start=None, end=None):
        co = self.trade_history(symbol, start, end)
        return self._sync_run_coroutine(co)

    async def trade_history(self, symbol: str = None, start=None, end=None):
        raise NotImplementedError

    def balances_sync(self):
        co = self.balances()
        return self._sync_run_coroutine(co)

    async def balances(self):
        raise NotImplementedError

    def positions_sync(self, **kwargs):
        co = self.positions(**kwargs)
        return self._sync_run_coroutine(co)

    async def positions(self, **kwargs):
        raise NotImplementedError

    def ledger_sync(self, aclass=None, asset=None, ledger_type=None, start=None, end=None):
        co = self.ledger(aclass, asset, ledger_type, start, end)
        return self._sync_run_coroutine(co)

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
