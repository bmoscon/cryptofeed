'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect
from collections import defaultdict
from contextlib import suppress
import logging
from typing import Tuple, Callable, List, Union

from aiohttp.typedefs import StrOrURL

from cryptofeed.callback import Callback
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, WSAsyncConn
from cryptofeed.connection_handler import ConnectionHandler
from cryptofeed.defines import BALANCES, CANDLES, FUNDING, INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, ORDER_INFO, POSITIONS, TICKER, TRADES, FILLS
from cryptofeed.exceptions import BidAskOverlapping
from cryptofeed.exchange import Exchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger(__name__)


class Feed(Exchange):
    def __init__(self, candle_interval=None, candle_closed_only=True, timeout=120, timeout_interval=30, retries=10, symbols=None, channels=None, subscription=None, callbacks=None, max_depth=0, checksum_validation=False, cross_check=False, exceptions=None, log_message_on_error=False, delay_start=0, http_proxy: StrOrURL = None, shutdown_timeout=10.0, **kwargs):
        """
        candle_interval: str
            the candle interval. See the specific exchange to see what intervals they support.
            Defaults to 1m where the venue supports it, otherwise to the venue's shortest
            supported interval - some venues offer exactly one (Coinbase publishes 5m only)
        candle_closed_only: bool
            returns only closed/completed candles (if supported by exchange).
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
        exceptions: list of exceptions
            These exceptions will not be handled internally and will propagate out of the feed.
        log_message_on_error: bool
            If an exception is encountered in the connection handler, log the raw message
        delay_start: int, float
            a delay before starting the feed/connection to the exchange. If you are subscribing to a large number of feeds
            on a single exchange, you may encounter 429s. You can use this to stagger the starts.
        http_proxy: str
            URL of proxy server. Passed to HTTPPoll and HTTPAsyncConn. Only used for HTTP GET requests.
        shutdown_timeout: float
            Deadline, in seconds, for flushing backends during graceful shutdown
        """
        super().__init__(**kwargs)
        self.log_on_error = log_message_on_error
        self.retries = retries
        self.exceptions = exceptions
        self.connection_handlers = []
        self.timeout = timeout
        self.timeout_interval = timeout_interval
        self.subscription = defaultdict(set)
        self.cross_check = cross_check
        self.normalized_symbols = []
        self.max_depth = max_depth
        self.previous_book = defaultdict(dict)
        self.checksum_validation = checksum_validation
        self.requires_authentication = False
        self._feed_config = defaultdict(list)
        self.http_conn = HTTPAsyncConn(self.id, http_proxy)
        self.http_proxy = http_proxy
        self.start_delay = delay_start
        self.candle_closed_only = candle_closed_only
        self.shutdown_timeout = shutdown_timeout
        self._sequence_no = {}
        self._conn_tg = None
        self._spawned = set()
        self._poller_tasks = []

        if self.valid_candle_intervals != NotImplemented:
            if candle_interval is None:
                candle_interval = '1m' if '1m' in self.valid_candle_intervals else sorted(self.valid_candle_intervals)[0]
            elif candle_interval not in self.valid_candle_intervals:
                raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        elif candle_interval is None:
            candle_interval = '1m'
        self.candle_interval = candle_interval

        if self.candle_interval_map != NotImplemented:
            self.normalize_candle_interval = {value: key for key, value in self.candle_interval_map.items()}

        if subscription is not None and (symbols is not None or channels is not None):
            raise ValueError("Use subscription, or channels and symbols, not both")

        self._init_subscription = subscription
        self._init_symbols = symbols
        self._init_channels = channels

        if subscription is not None:
            for channel in subscription:
                self.std_channel_to_exchange(channel)
                if self.is_authenticated_channel(channel):
                    if not self.key_id or not self.key_secret:
                        raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
                    self.requires_authentication = True
                self.normalized_symbols.extend(subscription[channel])
                self._feed_config[channel].extend(self.normalized_symbols)

        if symbols and channels:
            if any(self.is_authenticated_channel(chan) for chan in channels):
                if not self.key_id or not self.key_secret:
                    raise ValueError("Authenticated channel subscribed to, but no auth keys provided")
                self.requires_authentication = True

            [self._feed_config[channel].extend(symbols) for channel in channels]
            self.normalized_symbols = symbols
            self.normalized_channels = channels

        self._feed_config = dict(self._feed_config)
        self._auth_token = None

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
                callback = [callback]
            for cb in callback:
                if not (inspect.iscoroutinefunction(cb) or inspect.iscoroutinefunction(getattr(cb, '__call__', None))):
                    raise TypeError(f'{key} callback on {self.id} must be async - wrap synchronous callables in ExecutorCallback')
            self.callbacks[key] = callback

        if self.normalized_symbol_mapping is not None:
            self._build_subscription()

    def _build_subscription(self):
        self._ensure_symbol_mapping()

        if self._init_subscription is not None:
            self.subscription = defaultdict(set)
            for channel in self._init_subscription:
                chan = self.std_channel_to_exchange(channel)
                self.subscription[chan].update([self.std_symbol_to_exchange_symbol(symbol) for symbol in self._init_subscription[channel]])

        if self._init_symbols and self._init_channels:
            symbols = [self.std_symbol_to_exchange_symbol(symbol) for symbol in self._init_symbols]
            channels = list(set([self.std_channel_to_exchange(chan) for chan in self._init_channels]))
            self.subscription = {chan: symbols for chan in channels}

        self._subscription_resolved()

    def _subscription_resolved(self):
        pass

    async def _setup(self):
        await self.load_symbols(conn=self.http_conn, cache_ttl=self.config.symbol_cache_ttl or None)
        self._ensure_symbol_mapping()
        self._build_subscription()

    async def _pre_connect(self):
        pass

    async def validate(self):
        await self._setup()

    async def run(self, stop_event: asyncio.Event):
        try:
            await self._run(stop_event)
        finally:
            # every exit path - clean, failed, or cancelled - releases the http session
            with suppress(Exception):
                await self.http_conn.close()

    async def _run(self, stop_event: asyncio.Event):
        await self._setup()
        await self._pre_connect()

        self.connection_handlers = []
        for conn, sub, handler, auth in self.connect():
            self.connection_handlers.append(ConnectionHandler(conn, sub, handler, auth, self.retries, timeout=self.timeout, timeout_interval=self.timeout_interval, exceptions=self.exceptions, log_on_error=self.log_on_error, start_delay=self.start_delay))
        self._spawned = set()
        self._poller_tasks = []

        async with asyncio.TaskGroup() as tg:
            writer_tasks = []
            for callbacks in self.callbacks.values():
                for cb in callbacks:
                    if hasattr(cb, 'start_writer'):
                        task = cb.start_writer(tg, name=f'feed.{self.id}.backend.{self.backend_name(cb)}')
                        if task is not None:
                            writer_tasks.append(task)

            error = None
            try:
                async with asyncio.TaskGroup() as conn_tg:
                    self._conn_tg = conn_tg
                    for handler in self.connection_handlers:
                        conn_tg.create_task(handler.run(), name=f'feed.{self.id}.conn.{handler.conn.id}')
                    conn_tg.create_task(self._stop_on_event(stop_event), name=f'feed.{self.id}.stop-watch')
            except Exception as e:
                error = e
            finally:
                self._conn_tg = None

            try:
                async with asyncio.timeout(self.shutdown_timeout):
                    await self.shutdown()
                    if writer_tasks:
                        await asyncio.wait(writer_tasks)
            except TimeoutError:
                LOG.warning('%s: backend flush exceeded the %.1fs shutdown deadline - cancelling writers', self.id, self.shutdown_timeout)
                for task in writer_tasks:
                    task.cancel()

            if error is not None:
                raise error

    async def _stop_on_event(self, stop_event: asyncio.Event):
        await stop_event.wait()
        LOG.info('%s: stop requested - closing connections', self.id)
        for task in self._poller_tasks:
            task.cancel()
        for handler in self.connection_handlers:
            await handler.request_stop()

    def _spawn(self, name: str, coro):
        # Spawn a named task owned by the feed's connection TaskGroup
        task_name = f'feed.{self.id}.poll.{name}'
        if self._conn_tg is None:
            LOG.warning('%s: not running under a supervision tree - poller %s not started', self.id, task_name)
            coro.close()
            return
        if task_name in self._spawned:
            coro.close()
            return
        self._spawned.add(task_name)
        self._poller_tasks.append(self._conn_tg.create_task(coro, name=task_name))

    def _connect_rest(self):
        """
        Child classes should override this method to generate connection objects that
        support their polled REST endpoints.
        """
        return []

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        """
        Generic websocket connection method for exchanges. Uses the websocket endpoints defined in the
        exchange to determine, based on the subscription information, which endpoints should be used,
        and what instruments/channels should be enabled on each connection.

        Connect returns a list of tuples. Each tuple contains
        1. an AsyncConnection object
        2. the subscribe function pointer associated with this connection
        3. the message handler for this connection
        4. The authentication method for this connection
        """
        def limit_sub(subscription: dict, limit: int, auth, options: dict):
            ret = []
            sub = {}
            for channel in subscription:
                for pair in subscription[channel]:
                    if channel not in sub:
                        sub[channel] = []
                    sub[channel].append(pair)
                    if sum(map(len, sub.values())) == limit:
                        ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=sub, **options), self.subscribe, self.message_handler, self.authenticate))
                        sub = {}

            if sum(map(len, sub.values())) > 0:
                ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=sub, **options), self.subscribe, self.message_handler, self.authenticate))
            return ret

        ret = self._connect_rest()
        for endpoint in self.websocket_endpoints:
            auth = None
            if endpoint.authentication:
                # if a class has an endpoint with the authentication flag set to true, this
                # method must be define. The method will be called immediately before connecting
                # to authenticate the connection. _ws_authentication returns a tuple of address and ws options
                auth = self._ws_authentication
            limit = endpoint.limit
            addr = self._address()
            addr = endpoint.get_address(self.sandbox) if addr is None else addr
            if not addr:
                continue

            # filtering can only be done on normalized symbols, but this subscription needs to have the raw/exchange specific
            # subscription, so we need to temporarily convert the symbols back and forth. It has to be done here
            # while in the context of the class
            temp_sub = {chan: [self.exchange_symbol_to_std_symbol(s) for s in symbols] for chan, symbols in self.subscription.items()}
            filtered_sub = {chan: [self.std_symbol_to_exchange_symbol(s) for s in symbols] for chan, symbols in endpoint.subscription_filter(temp_sub).items()}
            count = sum(map(len, filtered_sub.values()))

            if not self.allow_empty_subscriptions and (not filtered_sub or count == 0):
                continue
            if limit and count > limit:
                ret.extend(limit_sub(filtered_sub, limit, auth, endpoint.options))
            else:
                if isinstance(addr, list):
                    for add in addr:
                        ret.append((WSAsyncConn(add, self.id, authentication=auth, subscription=filtered_sub, **endpoint.options), self.subscribe, self.message_handler, self.authenticate))
                else:
                    ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=filtered_sub, **endpoint.options), self.subscribe, self.message_handler, self.authenticate))

        return ret

    def _ws_authentication(self, address: str, ws_options: dict) -> Tuple[str, dict]:
        '''
        Used to do authentication immediately before connecting. Takes the address and the websocket options as
        arguments and returns a new address and new websocket options that will be used to connect.
        '''
        raise NotImplementedError

    def _address(self):
        '''
        If you need to dynamically calculate the address before connecting, overload this method in the exchange object.
        '''
        return None

    @property
    def address(self) -> Union[List, str]:
        if len(self.websocket_endpoints) == 0:
            return
        addrs = [ep.get_address(sandbox=self.sandbox) for ep in self.websocket_endpoints]
        return addrs[0] if len(addrs) == 1 else addrs

    async def book_callback(self, book_type: str, book: OrderBook, receipt_timestamp: float, timestamp=None, raw=None, sequence_number=None, checksum=None, delta=None):
        if self.cross_check:
            self.check_bid_ask_overlapping(book)

        book.timestamp = timestamp
        book.raw = raw
        book.sequence_number = sequence_number
        book.delta = delta
        book.checksum = checksum
        await self.callback(book_type, book, receipt_timestamp)

    def check_bid_ask_overlapping(self, data):
        bid, ask = data.book.bids, data.book.asks
        if len(bid) > 0 and len(ask) > 0:
            best_bid, best_ask = bid.index(0)[0], ask.index(0)[0]
            if best_bid >= best_ask:
                raise BidAskOverlapping(f"{self.id} - {data.symbol}: best bid {best_bid} >= best ask {best_ask}")

    async def callback(self, data_type, obj, receipt_timestamp):
        for cb in self.callbacks[data_type]:
            await cb(obj, receipt_timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        raise NotImplementedError

    async def subscribe(self, connection: AsyncConnection):
        raise NotImplementedError

    async def authenticate(self, connection: AsyncConnection):
        pass

    async def shutdown(self):
        LOG.info('%s: feed shutdown starting...', self.id)
        await self.http_conn.close()

        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'stop'):
                    LOG.info('%s: stopping backend %s', self.id, self.backend_name(callback))
                    await callback.stop()
        for c in self.connection_handlers:
            await c.conn.close()
        LOG.info('%s: feed shutdown completed', self.id)

    def backend_name(self, callback):
        if hasattr(callback, '__class__'):
            if hasattr(callback, 'handler'):
                return callback.handler.__class__.__name__ + "+" + callback.__class__.__name__
            return callback.__class__.__name__
        return callback.__name__
