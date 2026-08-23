'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from collections import defaultdict
import os
import time
from datetime import datetime as dt, timezone
from decimal import Decimal
from typing import Dict, List, Union

from cryptofeed import _json as json
from cryptofeed.symbols import Symbol, Symbols
from cryptofeed.connection import HTTPAsyncConn, RestEndpoint
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol
from cryptofeed.config import Config


LOG = logging.getLogger(__name__)


class Exchange:
    provides_checksum = False
    provides_sequence_number = False
    validates_sequence_number = False
    book_delivery = 'delta'
    _unknown_categories = defaultdict(set)

    @classmethod
    def unsupported_category(cls, field: str, value) -> None:
        seen = Exchange._unknown_categories[cls.id]
        if value in seen:
            return
        seen.add(value)
        LOG.warning('%s: unrecognised %s %r - skipping. symbol parser needs updating', cls.id, field, value)

    id = NotImplemented
    websocket_endpoints = NotImplemented
    rest_endpoints = NotImplemented
    _parse_symbol_data = NotImplemented
    websocket_channels = NotImplemented
    request_limit = NotImplemented
    valid_candle_intervals = NotImplemented
    candle_interval_map = NotImplemented
    allow_empty_subscriptions = False

    def __init__(self, config=None, sandbox=False, **kwargs):
        self.config = Config(config=config)
        self.sandbox = sandbox
        self.ignore_invalid_instruments = self.config.ignore_invalid_instruments

        self.normalized_symbol_mapping = None
        self.exchange_symbol_mapping = None
        if Symbols.populated(self.id):
            self._apply_symbol_mapping()

    @classmethod
    def timestamp_normalize(cls, ts: Union[str, dt]) -> float:
        if isinstance(ts, str):
            ts = dt.fromisoformat(ts)
        return ts.astimezone(timezone.utc).timestamp()

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for the websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = {'websocket': list(cls.websocket_channels.keys())}
        return data

    @classmethod
    def symbols(cls, refresh=False) -> list:
        return list(cls.symbol_mapping(refresh=refresh).keys())

    @classmethod
    async def _symbol_endpoint_prepare(cls, ep: RestEndpoint, conn: HTTPAsyncConn) -> Union[List[str], str]:
        """
        override if a specific exchange needs to do something first, like query an API
        to get a list of currencies, that are then used to build the list of symbol endpoints
        """
        return ep.route('instruments')

    SLOW_SYMBOL_FETCH_SECONDS = 5.0

    @classmethod
    async def _await_symbol_fetch(cls, awaitable, addr):
        async def fetch():
            return await awaitable

        task = asyncio.create_task(fetch(), name=f'{cls.id}.symbols')
        started = time.time()
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=cls.SLOW_SYMBOL_FETCH_SECONDS)
                if done:
                    elapsed = time.time() - started
                    if elapsed >= cls.SLOW_SYMBOL_FETCH_SECONDS:
                        LOG.warning("%s: symbol list from %s arrived after %.1fs", cls.id, addr, elapsed)
                    return task.result()
                LOG.warning("%s: still waiting for the symbol list from %s after %.0fs - no data delivered until symbols arrive", cls.id, addr, time.time() - started)
        except asyncio.CancelledError:
            task.cancel()
            raise

    @classmethod
    async def _fetch_symbol_data(cls, conn: HTTPAsyncConn) -> list:
        data = []
        for endpoint in cls.rest_endpoints:
            addr = await cls._symbol_endpoint_prepare(endpoint, conn)
            if isinstance(addr, list):
                LOG.debug("%s: reading symbol information from %s", cls.id, addr)
                fetched = await cls._await_symbol_fetch(asyncio.gather(*[conn.read(a) for a in addr]), addr)
                data.extend(json.loads(f, parse_float=Decimal) for f in fetched)
            else:
                LOG.debug("%s: reading symbol information from %s", cls.id, addr)
                data.append(json.loads(await cls._await_symbol_fetch(conn.read(addr), addr), parse_float=Decimal))
        return data

    @classmethod
    async def load_symbols(cls, conn: HTTPAsyncConn = None, refresh=False, cache_ttl: float = None) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        if not refresh and cache_ttl and cls._load_symbol_cache(cache_ttl):
            return Symbols.get(cls.id)[0]

        owns_conn = conn is None
        if owns_conn:
            conn = HTTPAsyncConn(cls.id)
        try:
            data = await cls._fetch_symbol_data(conn)
            syms, info = cls._parse_symbol_data(data if len(data) > 1 else data[0])
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise
        finally:
            if owns_conn:
                await conn.close()

        Symbols.set(cls.id, syms, info)
        cls._write_symbol_cache(syms, info)
        return syms

    @classmethod
    def symbol_mapping(cls, refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(cls.load_symbols(refresh=refresh))
        raise RuntimeError(f'{cls.id}: symbols cannot be loaded synchronously - use await {cls.__name__}.load_symbols()')

    @staticmethod
    def _symbol_cache_path(exchange_id: str) -> str:
        base = os.environ.get('XDG_CACHE_HOME') or os.path.join(os.path.expanduser('~'), '.cache')
        return os.path.join(base, 'cryptofeed', 'symbols', f'{exchange_id}.json')

    @classmethod
    def _load_symbol_cache(cls, ttl: float) -> bool:
        try:
            with open(cls._symbol_cache_path(cls.id), 'r') as fp:
                cached = json.loads(fp.read(), parse_float=Decimal)
            if time.time() - float(cached['timestamp']) > ttl:
                return False
            Symbols.set(cls.id, cached['symbols'], cached['info'])
            return True
        except (OSError, ValueError, KeyError, TypeError):
            return False

    @classmethod
    def _write_symbol_cache(cls, syms: dict, info: dict):
        path = cls._symbol_cache_path(cls.id)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as fp:
                fp.write(json.dumps({'timestamp': time.time(), 'symbols': syms, 'info': info}))
        except (OSError, TypeError, ValueError):
            LOG.warning('%s: unable to write symbol cache', cls.id, exc_info=True)

    def _apply_symbol_mapping(self):
        self.normalized_symbol_mapping, _ = Symbols.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

    def _ensure_symbol_mapping(self):
        if self.normalized_symbol_mapping is None:
            if not Symbols.populated(self.id):
                raise RuntimeError(f'{self.id}: symbols not loaded')
            self._apply_symbol_mapping()

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

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        self._ensure_symbol_mapping()
        try:
            return self.exchange_symbol_mapping[symbol]
        except KeyError:
            if self.ignore_invalid_instruments:
                LOG.warning('Invalid symbol %s configured for %s', symbol, self.id)
                return symbol
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    def std_symbol_to_exchange_symbol(self, symbol: Union[str, Symbol]) -> str:
        self._ensure_symbol_mapping()
        if isinstance(symbol, Symbol):
            symbol = symbol.normalized
        try:
            return self.normalized_symbol_mapping[symbol]
        except KeyError:
            if self.ignore_invalid_instruments:
                LOG.warning('Invalid symbol %s configured for %s', symbol, self.id)
                return symbol
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')
