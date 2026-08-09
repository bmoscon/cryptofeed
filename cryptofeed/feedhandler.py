'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from contextlib import suppress
from difflib import get_close_matches
from signal import SIGABRT, SIGINT, SIGTERM
from typing import List

try:
    # unix / macos only
    from signal import SIGHUP
    SIGNALS = (SIGABRT, SIGINT, SIGTERM, SIGHUP)
except ImportError:
    SIGNALS = (SIGABRT, SIGINT, SIGTERM)

from cryptofeed import _json as json
from cryptofeed.config import Config
from cryptofeed.connection import Connection
from cryptofeed.defines import L2_BOOK
from cryptofeed.feed import Feed
from cryptofeed.log import configure_logging
from cryptofeed.nbbo import NBBO
from cryptofeed.exchanges import EXCHANGE_MAP


LOG = logging.getLogger(__name__)


class FeedHandler:
    def __init__(self, config=None, raw_data_collection=None, on_feed_error='raise'):
        """
        config: str, dict or None
            if str, absolute path (including file name) of the config file. If not provided, config can also be a dictionary of values, or
            can be None, which will default options. See docs/config.md for more information.
        raw_data_collection: callback (see AsyncFileCallback) or None
            if set, enables collection of raw data from exchanges. ALL https/wss traffic from the exchanges will be collected.
        on_feed_error: 'raise' or 'remove_feed'
            'raise', default - a feed that fails permanently stops the handler, cancelling other feeds
            'remove_feed' - the failed feed is flushed and removed, other feeds keep running.
        """
        if on_feed_error not in ('raise', 'remove_feed'):
            raise ValueError("on_feed_error must be 'raise' or 'remove_feed'")
        self.feeds = []
        self.config = Config(config=config)
        self.on_feed_error = on_feed_error
        self.raw_data_collection = None
        self._stop_event = None
        self._tg = None
        self._main_task = None
        self._signals_installed = False
        if raw_data_collection:
            Connection.raw_data_callback = raw_data_collection
            self.raw_data_collection = raw_data_collection

        if not self.config.log.disabled:
            configure_logging(filename=self.config.log.filename or None, level=self.config.log.level or 'WARNING', stream=True)

        if self.config.log_msg:
            LOG.info(self.config.log_msg)

        self._check_config_keys()

    _KNOWN_CONFIG_KEYS = frozenset(('log', 'uvloop', 'ignore_invalid_instruments', 'symbol_cache_ttl'))

    def _check_config_keys(self):
        known = self._KNOWN_CONFIG_KEYS | {exchange.lower() for exchange in EXCHANGE_MAP}
        for key in self.config.keys():
            if key not in known:
                close = get_close_matches(key, known, n=1)
                hint = f" - did you mean '{close[0]}'?" if close else ''
                LOG.warning("Config: unknown top-level key '%s'%s", key, hint)

    @property
    def running(self) -> bool:
        return self._tg is not None

    def add_feed(self, feed, **kwargs):
        """
        feed: str or class
            the feed (exchange) to add to the handler
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        if isinstance(feed, str):
            if feed in EXCHANGE_MAP:
                self.feeds.append(EXCHANGE_MAP[feed](config=self.config, **kwargs))
            else:
                raise ValueError("Invalid feed specified")
        else:
            self.feeds.append(feed)
        if self.raw_data_collection:
            self.raw_data_collection.write_header(self.feeds[-1].id, json.dumps(self.feeds[-1]._feed_config))

        if self._tg is not None:
            # while running (loop thread only) the new feed joins the live supervision tree
            self._tg.create_task(self._run_feed(self.feeds[-1]), name=f'feed.{self.feeds[-1].id}')

    def add_nbbo(self, feeds: List[Feed], symbols: List[str], callback, config=None):
        """
        feeds: list of feed classes
            list of feeds (exchanges) that comprises the NBBO
        symbols: list str
            the trading symbols
        callback: function pointer
            the callback to be invoked when a new tick is calculated for the NBBO
        config: dict, str, or None
            optional information to pass to each exchange that is part of the NBBO feed
        """
        cb = NBBO(callback, symbols)
        for feed in feeds:
            self.add_feed(feed(channels=[L2_BOOK], symbols=symbols, callbacks={L2_BOOK: cb}, config=config))

    def run(self, install_signal_handlers: bool = True):
        """Blocking convenience wrapper around run_async()

        install_signal_handlers: bool, default True
            if True, installs signal handlers that trigger a graceful shutdown on the
            first signal and a cancellation on the second. This can only be done
            from the main thread. when running cryptofeed on a child thread pass False
            and call request_stop() from your own handler.
        """
        loop_factory = None
        if self.config.uvloop:
            try:
                import uvloop
                loop_factory = uvloop.new_event_loop
                LOG.info('FH: using uvloop')
            except ImportError:
                LOG.info('FH: uvloop not installed')
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            runner.run(self.run_async(install_signal_handlers=install_signal_handlers))

    async def run_async(self, install_signal_handlers: bool = True):
        """
        async entry point

        Runs until request_stop() is called (or a signal arrives), a feed fails
        permanently with on_feed_error='raise', or the task is cancelled
        """
        self._stop_event = asyncio.Event()
        self._main_task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        if install_signal_handlers:
            self._install_signal_handlers(loop)
        try:
            async with asyncio.TaskGroup() as tg:
                self._tg = tg
                for feed in self.feeds:
                    tg.create_task(self._run_feed(feed), name=f'feed.{feed.id}')
        finally:
            self._tg = None
            self._main_task = None
            if install_signal_handlers:
                self._remove_signal_handlers(loop)
            if self.raw_data_collection:
                LOG.info('FH: shutting down raw data collection')
                self.raw_data_collection.stop()
            LOG.info('FH: leaving run_async()')

    def request_stop(self):
        if self._stop_event is not None:
            self._stop_event.set()

    async def _run_feed(self, feed):
        try:
            await feed.run(self._stop_event)
        except Exception:
            if self.on_feed_error == 'remove_feed':
                LOG.exception('FH: feed %s failed and was removed; remaining feeds continue', feed.id)
                if feed in self.feeds:
                    self.feeds.remove(feed)
                return
            raise

    def _on_signal(self):
        if self._stop_event is None:
            return
        if self._stop_event.is_set():
            LOG.warning('FH: second stop signal received - cancelling')
            if self._main_task is not None:
                self._main_task.cancel()
        else:
            LOG.info('FH: stop signal received - shutting down gracefully')
            self._stop_event.set()

    def _install_signal_handlers(self, loop):
        for sig in SIGNALS:
            loop.add_signal_handler(sig, self._on_signal)
        self._signals_installed = True

    def _remove_signal_handlers(self, loop):
        if not self._signals_installed:
            return
        for sig in SIGNALS:
            with suppress(Exception):
                loop.remove_signal_handler(sig)
        self._signals_installed = False
