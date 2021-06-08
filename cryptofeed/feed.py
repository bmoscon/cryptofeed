'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from functools import partial
import logging
import os
from typing import Dict, Tuple, Callable, Union, List

from cryptofeed.symbols import Symbols
from cryptofeed.callback import Callback
from cryptofeed.config import Config
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, HTTPSync, WSAsyncConn
from cryptofeed.connection_handler import ConnectionHandler
from cryptofeed.defines import (ASK, BID, BOOK_DELTA, CANDLES, FUNDING, FUTURES_INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS,
                                OPEN_INTEREST, MARKET_INFO, ORDER_INFO, TICKER, TRADES)
from cryptofeed.exceptions import BidAskOverlapping, UnsupportedDataFeed, UnsupportedSymbol
from cryptofeed.standards import feed_to_exchange, is_authenticated_channel
from cryptofeed.util.book import book_delta, depth


LOG = logging.getLogger('feedhandler')


class Feed:
    id = 'NotImplemented'
    http_sync = HTTPSync()

    def __init__(self, address: Union[dict, str], timeout=120, timeout_interval=30, retries=10, symbols=None, channels=None, subscription=None, config: Union[Config, dict, str] = None, callbacks=None, max_depth=None, book_interval=1000, snapshot_interval=False, checksum_validation=False, cross_check=False, origin=None, exceptions=None, log_message_on_error=False, sandbox=False):
        """
        address: str, or dict
            address to be used to create the connection.
            The address protocol (wss or https) will be used to determine the connection type.
            Use a "str" to pass one single address, or a dict of option/address
        timeout: int
            Time, in seconds, between message to wait before a feed is considered dead and will be restarted.
            Set to -1 for infinite.
        timeout_interval: int
            Time, in seconds, between timeout checks.
        retries: int
            Number of times to retry a failed connection. Set to -1 for infinite
        max_depth: int
            Maximum number of levels per side to return in book updates
        book_interval: int
            Number of updates between snapshots. Only applicable when book deltas are enabled.
            Book deltas are enabled by subscribing to the book delta callback.
        snapshot_interval: bool/int
            Number of updates between snapshots. Only applicable when book delta is not enabled.
            Updates between snapshots are not delivered to the client
        checksum_validation: bool
            Toggle checksum validation, when supported by an exchange.
        cross_check: bool
            Toggle a check for a crossed book. Should not be needed on exchanges that support
            checksums or provide message sequence numbers.
        origin: str
            Passed into websocket connect. Sets the origin header.
        exceptions: list of exceptions
            These exceptions will not be handled internally and will be passed to the asyncio exception handler. To
            handle them feedhandler will need to be supplied with a custom exception handler. See the `run` method
            on FeedHandler, specifically the `exception_handler` keyword argument.
        log_message_on_error: bool
            If an exception is encountered in the connection handler, log the raw message
        sandbox: bool
            enable sandbox mode for exchanges that support this
        """
        if isinstance(config, Config):
            LOG.info('%s: reuse object Config containing the following main keys: %s', self.id, ", ".join(config.config.keys()))
            self.config = config
        else:
            LOG.info('%s: create Config from type: %r', self.id, type(config))
            self.config = Config(config)

        self.sandbox = sandbox

        self.log_on_error = log_message_on_error
        self.retries = retries
        self.exceptions = exceptions
        self.connection_handlers = []
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.subscription = defaultdict(set)
        self.address = address
        self.book_update_interval = book_interval
        self.snapshot_interval = snapshot_interval
        self.cross_check = cross_check
        self.updates = defaultdict(int)
        self.do_deltas = False
        self.normalized_symbols = []
        self.max_depth = max_depth
        self.previous_book = defaultdict(dict)
        self.origin = origin
        self.checksum_validation = checksum_validation
        self.ws_defaults = {'ping_interval': 10, 'ping_timeout': None, 'max_size': 2**23, 'max_queue': None, 'origin': self.origin}
        self.key_id = os.environ.get(f'CF_{self.id}_KEY_ID') or self.config[self.id.lower()].key_id
        self.key_secret = os.environ.get(f'CF_{self.id}_KEY_SECRET') or self.config[self.id.lower()].key_secret
        self.key_passphrase = os.environ.get(f'CF_{self.id}_KEY_PASSWORD') or self.config[self.id.lower()].key_passphrase
        self._feed_config = defaultdict(list)
        self.http_conn = HTTPAsyncConn(self.id)

        symbols_cache = Symbols
        if not symbols_cache.populated(self.id):
            self.symbol_mapping()

        self.normalized_symbol_mapping, self.exchange_info = symbols_cache.get(self.id)
        self.exchange_symbol_mapping = {value: key for key, value in self.normalized_symbol_mapping.items()}

        if subscription is not None and (symbols is not None or channels is not None):
            raise ValueError("Use subscription, or channels and symbols, not both")

        if subscription is not None:
            for channel in subscription:
                chan = feed_to_exchange(self.id, channel)
                if is_authenticated_channel(channel):
                    if not self.key_id or not self.key_secret:
                        raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
                self.normalized_symbols.extend(subscription[channel])
                self.subscription[chan].update([self.std_symbol_to_exchange_symbol(symbol) for symbol in subscription[channel]])
                self._feed_config[channel].extend(self.normalized_symbols)

        if symbols and channels:
            if any(is_authenticated_channel(chan) for chan in channels):
                if not self.key_id or not self.key_secret:
                    raise ValueError("Authenticated channel subscribed to, but no auth keys provided")

            # if we dont have a subscription dict, we'll use symbols+channels and build one
            [self._feed_config[channel].extend(symbols) for channel in channels]
            self.normalized_symbols = symbols

            symbols = [self.std_symbol_to_exchange_symbol(symbol) for symbol in symbols]
            channels = list(set([feed_to_exchange(self.id, chan) for chan in channels]))
            self.subscription = {chan: symbols for chan in channels}

        self._feed_config = dict(self._feed_config)

        self.l3_book = {}
        self.l2_book = {}
        self.callbacks = {FUNDING: Callback(None),
                          FUTURES_INDEX: Callback(None),
                          L2_BOOK: Callback(None),
                          L3_BOOK: Callback(None),
                          LIQUIDATIONS: Callback(None),
                          OPEN_INTEREST: Callback(None),
                          MARKET_INFO: Callback(None),
                          TICKER: Callback(None),
                          TRADES: Callback(None),
                          CANDLES: Callback(None),
                          ORDER_INFO: Callback(None)
                          }

        if callbacks:
            for cb_type, cb_func in callbacks.items():
                self.callbacks[cb_type] = cb_func
                if cb_type == BOOK_DELTA:
                    self.do_deltas = True

        for key, callback in self.callbacks.items():
            if not isinstance(callback, list):
                self.callbacks[key] = [callback]

    def _connect_builder(self, address: str, options: list, header=None, sub=None, handler=None):
        """
        Helper method for building a custom connect tuple
        """
        subscribe = partial(self.subscribe if not sub else sub, options=options)
        conn = WSAsyncConn(address, self.id, extra_headers=header, **self.ws_defaults)
        return conn, subscribe, handler if handler else self.message_handler

    async def _empty_subscribe(self, conn: AsyncConnection, **kwargs):
        return

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        """
        Generic connection method for exchanges. Exchanges that require/support
        multiple addresses will need to override this method in their specific class
        unless they use the same subscribe method and message handler for all
        connections.

        Connect returns a list of tuples. Each tuple contains
        1. an AsyncConnection object
        2. the subscribe function pointer associated with this connection
        3. the message handler for this connection
        """
        ret = []
        if isinstance(self.address, str):
            return [(WSAsyncConn(self.address, self.id, **self.ws_defaults), self.subscribe, self.message_handler)]

        for _, addr in self.address.items():
            ret.append((WSAsyncConn(addr, self.id, **self.ws_defaults), self.subscribe, self.message_handler))
        return ret

    @classmethod
    def info(cls) -> dict:
        """
        Return information about the Exchange - what trading symbols are supported, what data channels, etc

        key_id: str
            API key to query the feed, required when requesting supported coins/symbols.
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = []
        for channel in (FUNDING, FUTURES_INDEX, LIQUIDATIONS, L2_BOOK, L3_BOOK, OPEN_INTEREST, MARKET_INFO, TICKER, TRADES, CANDLES):
            try:
                feed_to_exchange(cls.id, channel, silent=True)
                data['channels'].append(channel)
            except UnsupportedDataFeed:
                pass

        return data

    @classmethod
    def symbols(cls, refresh=False) -> dict:
        if refresh:
            cls.symbol_mapping(refresh=True)
        return cls.info()['symbols']

    @classmethod
    def symbol_mapping(cls, symbol_separator='-', refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            if isinstance(cls.symbol_endpoint, list):
                data = []
                for ep in cls.symbol_endpoint:
                    data.append(cls.http_sync.read(ep, json=True, uuid=cls.id))
            else:
                data = cls.http_sync.read(cls.symbol_endpoint, json=True, uuid=cls.id)
            syms, info = cls._parse_symbol_data(data, symbol_separator)
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

    async def book_callback(self, book: dict, book_type: str, symbol: str, forced: bool, delta: dict, timestamp: float, receipt_timestamp: float):
        """
        Three cases we need to handle here

        1.  Book deltas are enabled (application of max depth here is trivial)
        1a. Book deltas are enabled, max depth is not, and exchange does not support deltas. Rare
        2.  Book deltas not enabled, but max depth is enabled
        3.  Neither deltas nor max depth enabled
        4.  Book deltas disabled and snapshot intervals enabled (with/without max depth)

        2 and 3 can be combined into a single block as long as application of depth modification
        happens first

        For 1, need to handle separate cases where a full book is returned vs a delta
        """
        if self.do_deltas:
            if not forced and self.updates[symbol] < self.book_update_interval:
                if self.max_depth:
                    delta, book = await self.apply_depth(book, True, symbol)
                    if not (delta[BID] or delta[ASK]):
                        return
                elif not delta:
                    # this will only happen in cases where an exchange does not support deltas and max depth is not enabled.
                    # this is an uncommon situation. Exchanges that do not support deltas will need
                    # to populate self.previous internally to avoid the unncesessary book copy on all other exchanges
                    delta = book_delta(self.previous_book[symbol], book, book_type=book_type)
                    if not (delta[BID] or delta[ASK]):
                        return
                self.updates[symbol] += 1
                if self.cross_check:
                    self.check_bid_ask_overlapping(book, symbol)
                await self.callback(BOOK_DELTA, feed=self.id, symbol=symbol, delta=delta, timestamp=timestamp, receipt_timestamp=receipt_timestamp)
                if self.updates[symbol] != self.book_update_interval:
                    return
            elif forced and self.max_depth:
                # We want to send a full book update but need to apply max depth first
                _, book = await self.apply_depth(book, False, symbol)
        elif self.max_depth:
            if not self.snapshot_interval or (self.snapshot_interval and self.updates[symbol] >= self.snapshot_interval):
                changed, book = await self.apply_depth(book, False, symbol)
                if not changed:
                    return
        # case 4 - increment skipped update, and exit
        if self.snapshot_interval and self.updates[symbol] < self.snapshot_interval:
            self.updates[symbol] += 1
            return

        if self.cross_check:
            self.check_bid_ask_overlapping(book, symbol)
        if book_type == L2_BOOK:
            await self.callback(L2_BOOK, feed=self.id, symbol=symbol, book=book, timestamp=timestamp, receipt_timestamp=receipt_timestamp)
        else:
            await self.callback(L3_BOOK, feed=self.id, symbol=symbol, book=book, timestamp=timestamp, receipt_timestamp=receipt_timestamp)
        self.updates[symbol] = 0

    def check_bid_ask_overlapping(self, book, symbol):
        bid, ask = book[BID], book[ASK]
        if len(bid) > 0 and len(ask) > 0:
            best_bid, best_ask = bid.keys()[-1], ask.keys()[0]
            if best_bid >= best_ask:
                raise BidAskOverlapping(f"{self.id} {symbol} best bid {best_bid} >= best ask {best_ask}")

    async def callback(self, data_type, **kwargs):
        for cb in self.callbacks[data_type]:
            await cb(**kwargs)

    async def apply_depth(self, book: dict, do_delta: bool, symbol: str):
        ret = depth(book, self.max_depth)
        if not do_delta:
            delta = self.previous_book[symbol] != ret
            self.previous_book[symbol] = ret
            return delta, ret

        delta = book_delta(self.previous_book[symbol], ret)
        self.previous_book[symbol] = ret
        return delta, ret

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        raise NotImplementedError

    async def subscribe(self, connection: AsyncConnection, **kwargs):
        """
        kwargs will not be passed from anywhere, if you need to supply extra data to
        your subscribe, bind the data to the method with a partial
        """
        raise NotImplementedError

    async def shutdown(self):
        LOG.info('%s: feed shutdown starting...', self.id)
        await self.http_conn.close()

        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'stop'):
                    cb_name = callback.__class__.__name__ if hasattr(callback, '__class__') else callback.__name__
                    LOG.info('%s: stopping backend %s', self.id, cb_name)
                    await callback.stop()
        for c in self.connection_handlers:
            await c.conn.close()
        LOG.info('%s: feed shutdown completed', self.id)

    def stop(self):
        for c in self.connection_handlers:
            c.running = False

    def start(self, loop):
        """
        Create tasks for exchange interfaces and backends
        """
        for conn, sub, handler in self.connect():
            self.connection_handlers.append(ConnectionHandler(conn, sub, handler, self.retries, exceptions=self.exceptions, log_on_error=self.log_on_error))
            self.connection_handlers[-1].start(loop)

        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'start'):
                    cb_name = callback.__class__.__name__ if hasattr(callback, '__class__') else callback.__name__
                    LOG.info('%s: starting backend task %s', self.id, cb_name)
                    # Backends start tasks to write messages
                    callback.start(loop)

    def exchange_symbol_to_std_symbol(self, symbol: str) -> str:
        try:
            return self.exchange_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')

    def std_symbol_to_exchange_symbol(self, symbol: str) -> str:
        try:
            return self.normalized_symbol_mapping[symbol]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {self.id}')
