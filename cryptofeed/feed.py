'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from functools import partial
import logging
from typing import Tuple, Callable, Union, List

from aiohttp.typedefs import StrOrURL

from cryptofeed.callback import Callback
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, WSAsyncConn
from cryptofeed.connection_handler import ConnectionHandler
from cryptofeed.defines import BALANCES, CANDLES, FUNDING, INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, ORDER_INFO, POSITIONS, TICKER, TRADES, FILLS
from cryptofeed.exceptions import BidAskOverlapping
from cryptofeed.exchange import Exchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


class Feed(Exchange):
    def __init__(self, address: Union[dict, str], candle_interval='1m', timeout=120, timeout_interval=30, retries=10, symbols=None, channels=None, subscription=None, callbacks=None, max_depth=0, checksum_validation=False, cross_check=False, origin=None, exceptions=None, log_message_on_error=False, delay_start=0, http_proxy: StrOrURL = None, **kwargs):
        """
        address: str, or dict
            address to be used to create the connection.
            The address protocol (wss or https) will be used to determine the connection type.
            Use a "str" to pass one single address, or a dict of option/address
        candle_interval: str
            the candle interval. See the specific exchange to see what intervals they support
        timeout: int
            Time, in seconds, between message to wait before a feed is considered dead and will be restarted.
            Set to -1 for infinite.
        timeout_interval: int
            Time, in seconds, between timeout checks.
        retries: int
            Number of times to retry a failed connection. Set to -1 for infinite
        symbols: list of str, Symbol
            A list of instrument symbols. Symbols must be of type str or Symbol
        max_depth: int
            Maximum number of levels per side to return in book updates. 0 is the default, and indicates no trimming of levels should be performed.
        candle_interval: str
            Length of time between a candle's Open and Close. Valid on exchanges with support for candles
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
        delay_start: int, float
            a delay before starting the feed/connection to the exchange. If you are subscribing to a large number of feeds
            on a single exchange, you may encounter 429s. You can use this to stagger the starts.
        http_proxy: str
            URL of proxy server. Passed to HTTPPoll and HTTPAsyncConn. Only used for HTTP GET requests.
        """
        super().__init__(**kwargs)
        self.log_on_error = log_message_on_error
        self.retries = retries
        self.exceptions = exceptions
        self.connection_handlers = []
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.subscription = defaultdict(set)
        self.address = address
        self.cross_check = cross_check
        self.normalized_symbols = []
        self.max_depth = max_depth
        self.previous_book = defaultdict(dict)
        self.origin = origin
        self.checksum_validation = checksum_validation
        self.ws_defaults = {'ping_interval': 10, 'ping_timeout': None, 'max_size': 2**23, 'max_queue': None, 'origin': self.origin}
        self.requires_authentication = False
        self._feed_config = defaultdict(list)
        self.http_conn = HTTPAsyncConn(self.id, http_proxy)
        self.http_proxy = http_proxy
        self.start_delay = delay_start
        self.candle_interval = candle_interval

        if self.valid_candle_intervals != NotImplemented:
            if candle_interval not in self.valid_candle_intervals:
                raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")

        if subscription is not None and (symbols is not None or channels is not None):
            raise ValueError("Use subscription, or channels and symbols, not both")

        if subscription is not None:
            for channel in subscription:
                chan = self.std_channel_to_exchange(channel)
                if self.is_authenticated_channel(channel):
                    if not self.key_id or not self.key_secret:
                        raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
                    self.requires_authentication = True
                self.normalized_symbols.extend(subscription[channel])
                self.subscription[chan].update([self.std_symbol_to_exchange_symbol(symbol) for symbol in subscription[channel]])
                self._feed_config[channel].extend(self.normalized_symbols)

        if symbols and channels:
            if any(self.is_authenticated_channel(chan) for chan in channels):
                if not self.key_id or not self.key_secret:
                    raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
                self.requires_authentication = True

            # if we dont have a subscription dict, we'll use symbols+channels and build one
            [self._feed_config[channel].extend(symbols) for channel in channels]
            self.normalized_symbols = symbols

            symbols = [self.std_symbol_to_exchange_symbol(symbol) for symbol in symbols]
            channels = list(set([self.std_channel_to_exchange(chan) for chan in channels]))
            self.subscription = {chan: symbols for chan in channels}

        self._feed_config = dict(self._feed_config)

        self._l3_book = {}
        self._l2_book = {}
        self.callbacks = {FUNDING: Callback(None),
                          INDEX: Callback(None),
                          L2_BOOK: Callback(None),
                          L3_BOOK: Callback(None),
                          LIQUIDATIONS: Callback(None),
                          OPEN_INTEREST: Callback(None),
                          TICKER: Callback(None),
                          TRADES: Callback(None),
                          CANDLES: Callback(None),
                          ORDER_INFO: Callback(None),
                          FILLS: Callback(None),
                          BALANCES: Callback(None),
                          POSITIONS: Callback(None)
                          }

        if callbacks:
            for cb_type, cb_func in callbacks.items():
                self.callbacks[cb_type] = cb_func

        for key, callback in self.callbacks.items():
            if not isinstance(callback, list):
                self.callbacks[key] = [callback]

    def _connect_builder(self, address: str, options: list, header=None, sub=None, handler=None, auth=None):
        """
        Helper method for building a custom connect tuple
        """
        subscribe = partial(self.subscribe if not sub else sub, options=options)
        conn = WSAsyncConn(address, self.id, extra_headers=header, **self.ws_defaults)
        return conn, subscribe, handler if handler else self.message_handler, auth if auth else self.authenticate

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
            return [(WSAsyncConn(self.address, self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate)]

        for _, addr in self.address.items():
            ret.append((WSAsyncConn(addr, self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def book_callback(self, book_type: str, book: OrderBook, receipt_timestamp: float, timestamp=None, raw=None, sequence_number=None, checksum=None, delta=None):
        if self.cross_check:
            self.check_bid_ask_overlapping(book.book)

        book.timestamp = timestamp
        book.raw = raw
        book.sequence_number = sequence_number
        book.delta = delta
        book.checksum = checksum
        await self.callback(book_type, book, receipt_timestamp)

    def check_bid_ask_overlapping(self, book):
        bid, ask = book.bids, book.asks
        if len(bid) > 0 and len(ask) > 0:
            best_bid, best_ask = bid.index(0)[0], ask.index(0)[0]
            if best_bid >= best_ask:
                raise BidAskOverlapping(f"{self.id} - {book.symbol}: best bid {best_bid} >= best ask {best_ask}")

    async def callback(self, data_type, obj, receipt_timestamp):
        for cb in self.callbacks[data_type]:
            await cb(obj, receipt_timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        raise NotImplementedError

    async def subscribe(self, connection: AsyncConnection, **kwargs):
        """
        kwargs will not be passed from anywhere, if you need to supply extra data to
        your subscribe, bind the data to the method with a partial
        """
        raise NotImplementedError

    async def authenticate(self, connection: AsyncConnection):
        pass

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

    def start(self, loop: asyncio.AbstractEventLoop):
        """
        Create tasks for exchange interfaces and backends
        """
        for conn, sub, handler, auth in self.connect():
            self.connection_handlers.append(ConnectionHandler(conn, sub, handler, auth, self.retries, timeout=self.timeout, timeout_interval=self.timeout_interval, exceptions=self.exceptions, log_on_error=self.log_on_error, start_delay=self.start_delay))
            self.connection_handlers[-1].start(loop)

        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'start'):
                    cb_name = callback.__class__.__name__ if hasattr(callback, '__class__') else callback.__name__
                    LOG.info('%s: starting backend task %s', self.id, cb_name)
                    # Backends start tasks to write messages
                    callback.start(loop)
