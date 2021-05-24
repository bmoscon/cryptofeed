'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from cryptofeed.connection import Connection
import logging
import signal
from signal import SIGABRT, SIGINT, SIGTERM
import sys
from typing import List

try:
    # unix / macos only
    from signal import SIGHUP
    SIGNALS = (SIGABRT, SIGINT, SIGTERM, SIGHUP)
except ImportError:
    SIGNALS = (SIGABRT, SIGINT, SIGTERM)

from yapic import json

from cryptofeed.config import Config
from cryptofeed.defines import L2_BOOK
from cryptofeed.feed import Feed
from cryptofeed.log import get_logger
from cryptofeed.nbbo import NBBO
from cryptofeed.exchanges import EXCHANGE_MAP


LOG = logging.getLogger('feedhandler')


def setup_signal_handlers(loop):
    """
    This must be run from the loop in the main thread
    """
    def handle_stop_signals(*args):
        raise SystemExit
    if sys.platform.startswith('win'):
        # NOTE: asyncio loop.add_signal_handler() not supported on windows
        for sig in SIGNALS:
            signal.signal(sig, handle_stop_signals)
    else:
        for sig in SIGNALS:
            loop.add_signal_handler(sig, handle_stop_signals)


class FeedHandler:
    def __init__(self, config=None, raw_data_collection=None):
        """
        config: str, dict or None
            if str, absolute path (including file name) of the config file. If not provided, config can also be a dictionary of values, or
            can be None, which will default options. See docs/config.md for more information.
        raw_data_collection: callback (see AsyncFileCallback) or None
            if set, enables collection of raw data from exchanges. ALL https/wss traffic from the exchanges will be collected.
        """
        self.feeds = []
        self.config = Config(config=config)
        self.raw_data_collection = None
        if raw_data_collection:
            Connection.raw_data_callback = raw_data_collection
            self.raw_data_collection = raw_data_collection

        get_logger('feedhandler', self.config.log.filename, self.config.log.level)
        if self.config.log_msg:
            LOG.info(self.config.log_msg)

        if self.config.uvloop:
            try:
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                LOG.info('FH: uvloop initalized')
            except ImportError:
                LOG.info("FH: uvloop not initialized")

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
                self.feeds.append((EXCHANGE_MAP[feed](config=self.config, **kwargs)))
            else:
                raise ValueError("Invalid feed specified")
        else:
            self.feeds.append((feed))
        if self.raw_data_collection:
            self.raw_data_collection.write_header(self.feeds[-1].id, json.dumps(self.feeds[-1]._feed_config))

    def add_feed_running(self, feed, loop=None, **kwargs):
        """
        Add and start a new feed to a running instance of cryptofeed

        feed: str or class
            the feed (exchange) to add to the handler
        loop: None, or EventLoop
            the loop on which to add the tasks
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        self.add_feed(feed, **kwargs)

        if loop is None:
            loop = asyncio.get_event_loop()

        self.feeds[-1].start(loop)

    def add_nbbo(self, feeds: List[Feed], symbols: List[str], callback):
        """
        feeds: list of feed classes
            list of feeds (exchanges) that comprises the NBBO
        symbols: list str
            the trading symbols
        callback: function pointer
            the callback to be invoked when a new tick is calculated for the NBBO
        """
        cb = NBBO(callback, symbols)
        for feed in feeds:
            self.add_feed(feed(channels=[L2_BOOK], symbols=symbols, callbacks={L2_BOOK: cb}))

    def run(self, start_loop: bool = True, install_signal_handlers: bool = True, exception_handler=None):
        """
        start_loop: bool, default True
            if false, will not start the event loop.
        install_signal_handlers: bool, default True
            if True, will install the signal handlers on the event loop. This
            can only be done from the main thread's loop, so if running cryptofeed on
            a child thread, this must be set to false, and setup_signal_handlers must
            be called from the main/parent thread's event loop
        exception_handler: asyncio exception handler function pointer
            a custom exception handler for asyncio
        """
        if len(self.feeds) == 0:
            txt = f'FH: No feed specified. Please specify at least one feed among {list(EXCHANGE_MAP.keys())}'
            LOG.critical(txt)
            raise ValueError(txt)

        loop = asyncio.get_event_loop()
        # Good to enable when debugging or without code change: export PYTHONASYNCIODEBUG=1)
        # loop.set_debug(True)

        if install_signal_handlers:
            setup_signal_handlers(loop)

        for feed in self.feeds:
            feed.start(loop)

        if not start_loop:
            return

        try:
            if exception_handler:
                loop.set_exception_handler(exception_handler)
            loop.run_forever()
        except SystemExit:
            LOG.info('FH: System Exit received - shutting down')
        except Exception as why:
            LOG.exception('FH: Unhandled %r - shutting down', why)
        finally:
            self.stop(loop=loop)
            self.close(loop=loop)

        LOG.info('FH: leaving run()')

    def stop(self, loop=None):
        """Shutdown the Feed backends asynchronously."""
        if not loop:
            loop = asyncio.get_event_loop()

        LOG.info('FH: shutdown connections handlers in feeds')
        for feed in self.feeds:
            feed.stop()

        LOG.info('FH: create the tasks to properly shutdown the backends (to flush the local cache)')
        shutdown_tasks = []
        for feed in self.feeds:
            task = loop.create_task(feed.shutdown())
            try:
                task.set_name(f'shutdown_feed_{feed.id}')
            except AttributeError:
                # set_name only in 3.8+
                pass
            shutdown_tasks.append(task)

        LOG.info('FH: wait %s backend tasks until termination', len(shutdown_tasks))
        loop.run_until_complete(asyncio.gather(*shutdown_tasks))
        if self.raw_data_collection:
            LOG.info('FH: shutting down raw data collection')
            self.raw_data_collection.stop()

    def close(self, loop=None):
        """Stop the asynchronous generators and close the event loop."""
        if not loop:
            loop = asyncio.get_event_loop()

        LOG.info('FH: stop the AsyncIO loop')
        loop.stop()
        LOG.info('FH: run the AsyncIO event loop one last time')
        loop.run_forever()

        pending = asyncio.all_tasks(loop=loop)
        LOG.info('FH: cancel the %s pending tasks', len(pending))
        for task in pending:
            task.cancel()

        LOG.info('FH: run the pending tasks until complete')
        loop.run_until_complete(asyncio.gather(*pending, loop=loop, return_exceptions=True))

        LOG.info('FH: shutdown asynchronous generators')
        loop.run_until_complete(loop.shutdown_asyncgens())

        LOG.info('FH: close the AsyncIO loop')
        loop.close()
