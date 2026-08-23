'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import inspect
from collections import Counter, defaultdict
from contextlib import suppress
import logging
import time
from typing import Tuple, Callable, List, Union

from aiohttp import ClientError
from aiohttp.typedefs import StrOrURL

from cryptofeed.backends.aggregate import wrapper_chain
from cryptofeed.backends.backend import BackendQueue, RetryPolicy
from cryptofeed.callback import Callback
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, WSAsyncConn
from cryptofeed.connection_handler import ConnectionHandler
from cryptofeed.defines import CANDLES, FUNDING, INDEX, L1_BOOK, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, TICKER, TRADES
from cryptofeed.exceptions import BidAskOverlapping
from cryptofeed.exchange import Exchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger(__name__)


def _numbered(entries):
    out = []
    taken = set()
    for name, value in entries:
        if name in taken:
            index = 2
            while f'{name}#{index}' in taken:
                index += 1
            name = f'{name}#{index}'
        taken.add(name)
        out.append((name, value))
    return out


CALLBACK_CHANNELS = (FUNDING, INDEX, L1_BOOK, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, TICKER, TRADES, CANDLES)


class _BackendWriters:
    def __init__(self, feed: 'Feed', tg: asyncio.TaskGroup):
        self.feed = feed
        self.tg = tg

    def create_task(self, coro, name=None):
        return self.tg.create_task(self.feed._supervise_writer(coro, name), name=name)


class Feed(Exchange):
    keepalive_interval = None

    async def keepalive(self, conn: AsyncConnection):
        raise NotImplementedError(f'{self.id}: keepalive_interval is set but keepalive() is not implemented')

    def __init__(self, candle_interval=None, candle_closed_only=True, timeout=120, timeout_interval=30, retries=10, symbols=None, channels=None, subscription=None, callbacks=None, max_depth=0, checksum_validation=None, cross_check=False, exceptions=None, log_message_on_error=False, delay_start=0, http_proxy: StrOrURL = None, shutdown_timeout=10.0, **kwargs):
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
            Toggle checksum validation, when supported by an exchange. None (the default) takes the
            venue's own default from CHECKSUM_VALIDATION_DEFAULT - on where a checksum is the only
            gap detection the venue has, off elsewhere. Pass True or False to decide explicitly.
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
        self.subscription = defaultdict(list)
        self.checksum_validation = (self.CHECKSUM_VALIDATION_DEFAULT if checksum_validation is None else checksum_validation)
        self.cross_check = cross_check
        self.crossed_books = Counter()
        self._crossed_run = {}
        self.dead_pollers = []
        self.normalized_symbols = []
        self.max_depth = max_depth
        self.previous_book = defaultdict(dict)
        self._feed_config = defaultdict(list)
        self.http_conn = HTTPAsyncConn(self.id, http_proxy)
        self.http_proxy = http_proxy
        self._probe_conn = None
        self.start_delay = delay_start
        self.candle_closed_only = candle_closed_only
        self.shutdown_timeout = shutdown_timeout
        self._sequence_no = {}
        self._conn_tg = None
        self._spawned = set()
        self._poller_tasks = []
        self._backend_error = None
        self._stop_requested = None

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

        if subscription is None and bool(symbols) != bool(channels) and not self.allow_empty_subscriptions:
            raise ValueError("Invalid subscription")

        self._init_subscription = subscription
        self._init_symbols = symbols
        self._init_channels = channels

        if subscription is not None:
            for channel in subscription:
                self.std_channel_to_exchange(channel)
                self.normalized_symbols.extend(subscription[channel])
                self._feed_config[channel].extend(subscription[channel])

        if symbols and channels:
            for channel in channels:
                self.std_channel_to_exchange(channel)

            [self._feed_config[channel].extend(symbols) for channel in channels]
            self.normalized_symbols = symbols
            self.normalized_channels = channels

        self._feed_config = dict(self._feed_config)

        self._l3_book = {}
        self._l2_book = {}
        self.callbacks = {channel: Callback(None) for channel in CALLBACK_CHANNELS}

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
            self.subscription = {}
            seen = defaultdict(set)
            for channel in self._init_subscription:
                chan = self.std_channel_to_exchange(channel)
                bucket = self.subscription.setdefault(chan, [])
                for symbol in self._init_subscription[channel]:
                    exchange_symbol = self.std_symbol_to_exchange_symbol(symbol)
                    if exchange_symbol not in seen[chan]:
                        seen[chan].add(exchange_symbol)
                        bucket.append(exchange_symbol)

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
            with suppress(Exception):
                await self._close_probe_connection()

    async def _run(self, stop_event: asyncio.Event):
        await self._setup()
        await self._pre_connect()

        self.connection_handlers = []
        for conn, sub, handler in self.connect():
            self.connection_handlers.append(ConnectionHandler(conn, sub, handler, self.retries, timeout=self.timeout, timeout_interval=self.timeout_interval, exceptions=self.exceptions, log_on_error=self.log_on_error, start_delay=self.start_delay, keepalive=self.keepalive if self.keepalive_interval else None, keepalive_interval=self.keepalive_interval))
        if not self.connection_handlers and not self.allow_empty_subscriptions:
            LOG.warning('%s: empty subscription (subscription: %r)', self.id, dict(self.subscription))
        self._spawned = set()
        self._poller_tasks = []
        self._backend_error = None
        self._stop_requested = asyncio.Event()

        async with asyncio.TaskGroup() as tg:
            writers = _BackendWriters(self, tg)
            writer_tasks = []
            for callbacks in self.callbacks.values():
                for cb in callbacks:
                    if hasattr(cb, 'start_writer'):
                        task = cb.start_writer(writers, name=f'feed.{self.id}.backend.{self.backend_name(cb)}', owner=self)
                        if task is not None:
                            writer_tasks.append((cb, task))

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

            waiting_on = []
            try:
                async with asyncio.timeout(self.shutdown_timeout):
                    released = await self.shutdown()
                    waiting_on = [task for backend, task in writer_tasks if backend in released]
                    if waiting_on:
                        await asyncio.wait(waiting_on)
            except TimeoutError:
                LOG.warning('%s: backend flush exceeded the %.1fs shutdown deadline - cancelling writers', self.id, self.shutdown_timeout)
                for task in waiting_on:
                    task.cancel()

            if error is None:
                error = self._backend_error
            if error is not None:
                raise error

    async def _supervise_writer(self, coro, name: str):
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception as e:
            LOG.error('%s: backend writer %s failed', self.id, name, exc_info=True)
            if self._backend_error is None:
                self._backend_error = e
            self._stop_requested.set()

    async def _stop_on_event(self, stop_event: asyncio.Event):
        # either the handler asking every feed to stop, or this feed alone shutting down after one
        # of its own backend writers failed
        waiters = [asyncio.create_task(event.wait(), name=f'feed.{self.id}.stop-wait.{source}')
                   for source, event in (('handler', stop_event), ('backend', self._stop_requested))]
        try:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiter in waiters:
                waiter.cancel()
            await asyncio.gather(*waiters, return_exceptions=True)

        LOG.info('%s: stop requested - closing connections', self.id)

        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'begin_shutdown'):
                    callback.begin_shutdown()

        for task in self._poller_tasks:
            task.cancel()
        for handler in self.connection_handlers:
            await handler.request_stop()

    async def _supervise_poller(self, coro, name: str):
        policy = RetryPolicy(max_attempts=max(2, self.retries) if self.retries != -1 else 2 ** 31)
        attempt = 0
        while True:
            started = time.time()
            try:
                await coro()
                return
            except asyncio.CancelledError:
                raise
            except (ClientError, ConnectionError, OSError, asyncio.TimeoutError) as e:
                if time.time() - started >= self.RESTART_RESET_SECONDS:
                    attempt = 0

                attempt += 1
                if attempt >= policy.max_attempts:
                    LOG.error('%s: REST poller %s failed %d times without recovering - giving up on it. '
                              'The rest of the feed is unaffected', self.id, name, attempt, exc_info=True)
                    self._record_poller_death(name, f'{type(e).__name__}: {e}', attempt)
                    return

                delay = policy.delay(attempt)
                LOG.warning('%s: REST poller %s hit a transport error, restarting in %.1fs (attempt %d/%d) - '
                            '%s: %s', self.id, name, delay, attempt, policy.max_attempts, type(e).__name__, e)
                await asyncio.sleep(delay)

            except Exception as e:
                LOG.error('%s: REST poller %s raised something a retry cannot fix - stopping it. The '
                          'rest of the feed keeps running', self.id, name, exc_info=True)
                self._record_poller_death(name, f'{type(e).__name__}: {e}', attempt + 1)
                return


    RESTART_RESET_SECONDS = 300.0

    def _record_poller_death(self, name: str, error: str, attempts: int):
        self.dead_pollers.append({'poller': name, 'error': error[:300], 'attempts': attempts})

    def _spawn(self, name: str, factory, *args):
        task_name = f'feed.{self.id}.poll.{name}'
        if self._conn_tg is None:
            LOG.warning('%s: not running under a supervision tree - poller %s not started', self.id, task_name)
            return
        if task_name in self._spawned:
            return

        self._spawned.add(task_name)
        self._poller_tasks.append(self._conn_tg.create_task(self._supervise_poller(lambda: factory(*args), name), name=task_name))

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
                        ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=sub, **options), self.subscribe, self.message_handler))
                        sub = {}

            if sum(map(len, sub.values())) > 0:
                ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=sub, **options), self.subscribe, self.message_handler))
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
                        ret.append((WSAsyncConn(add, self.id, authentication=auth, subscription=filtered_sub, **endpoint.options), self.subscribe, self.message_handler))
                else:
                    ret.append((WSAsyncConn(addr, self.id, authentication=auth, subscription=filtered_sub, **endpoint.options), self.subscribe, self.message_handler))

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

    def _snapshot_url(self, symbol: str) -> str:
        raise NotImplementedError(f'{self.id} does not fetch a book snapshot over REST')


    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        raise NotImplementedError(f'{self.id} does not fetch a book snapshot over REST')


    # some exchanges **expect** occasional crossed books and their docs say to ignore this for
    # a few updates until it self corrects (scary)
    CROSSED_BOOK_TOLERANCE = 3
    CROSSED_BOOKS_ARE_DOCUMENTED = False

    async def book_callback(self, book_type: str, book: OrderBook, receipt_timestamp: float, timestamp=None, raw=None, sequence_number=None, checksum=None, delta=None):
        book.timestamp = timestamp
        book.raw = raw
        book.sequence_number = sequence_number
        book.delta = delta
        book.checksum = checksum

        crossed = self.check_bid_ask_overlapping(book)
        streak_key = (book_type, book.symbol)
        if crossed:
            self.crossed_books[book.symbol] += 1
            run = self._crossed_run.get(streak_key, 0) + 1
            self._crossed_run[streak_key] = run
        else:
            run = 0
            if self._crossed_run.get(streak_key):
                self._crossed_run[streak_key] = 0

        await self.callback(book_type, book, receipt_timestamp)

        if (crossed and self.cross_check and not self.CROSSED_BOOKS_ARE_DOCUMENTED and run >= self.CROSSED_BOOK_TOLERANCE):
            raise BidAskOverlapping(f"{self.id} - {book.symbol}: best bid {book.book.bids.index(0)[0]} > best ask {book.book.asks.index(0)[0]} for {run} consecutive updates")

    def check_bid_ask_overlapping(self, data) -> bool:
        bid, ask = data.book.bids, data.book.asks
        if len(bid) > 0 and len(ask) > 0:
            return bid.index(0)[0] > ask.index(0)[0]
        return False

    async def callback(self, data_type, obj, receipt_timestamp):
        for cb in self.callbacks[data_type]:
            await cb(obj, receipt_timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        raise NotImplementedError

    async def subscribe(self, connection: AsyncConnection):
        raise NotImplementedError

    async def shutdown(self):
        LOG.info('%s: feed shutdown starting...', self.id)
        await self.http_conn.close()
        await self._close_probe_connection()

        released = []
        for callbacks in self.callbacks.values():
            for callback in callbacks:
                if hasattr(callback, 'stop'):
                    LOG.info('%s: stopping backend %s', self.id, self.backend_name(callback))
                    if await callback.stop():
                        released.append(callback)
        for c in self.connection_handlers:
            await c.conn.close()
        LOG.info('%s: feed shutdown completed', self.id)
        return released

    def backend_name(self, callback):
        return '+'.join(type(node).__name__ for node in reversed(wrapper_chain(callback)))

    def backends(self) -> dict:
        return dict(_numbered(self._backend_entries()))

    def _backend_entries(self) -> list:
        entries = []
        seen = set()
        for callbacks in self.callbacks.values():
            for cb in callbacks:
                backend = next((node for node in wrapper_chain(cb) if isinstance(node, BackendQueue)), None)
                if backend is None or id(backend) in seen:
                    continue
                seen.add(id(backend))
                entries.append((self.backend_name(cb), backend))
        return entries

    def backend_stats(self) -> dict:
        return {name: backend.stats for name, backend in self.backends().items()}
