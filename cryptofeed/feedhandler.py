'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import signal
from signal import SIGABRT, SIGINT, SIGTERM
import sys

try:
    # unix / macos only
    from signal import SIGHUP
    SIGNALS = (SIGABRT, SIGINT, SIGTERM, SIGHUP)
except ImportError:
    SIGNALS = (SIGABRT, SIGINT, SIGTERM)

import zlib
from collections import defaultdict
from socket import error as socket_error
from time import time
from typing import List, Optional

from yapic import json

from websockets import ConnectionClosed
from websockets.exceptions import InvalidStatusCode

from cryptofeed.config import Config
from cryptofeed.defines import (BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BINANCE_US, BITCOINCOM, BITFINEX, BITFLYER,
                                BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, COINBASE, COINGECKO,
                                DERIBIT, FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN, KRAKEN_FUTURES, OKCOIN, OKEX, POLONIEX, PROBIT, UPBIT, WHALE_ALERT)
from cryptofeed.defines import EXX as EXX_str
from cryptofeed.defines import FTX as FTX_str
from cryptofeed.defines import L2_BOOK
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.exchanges import *
from cryptofeed.providers import *
from cryptofeed.log import get_logger
from cryptofeed.nbbo import NBBO


LOG = logging.getLogger('feedhandler')


# Maps string name to class name for use with config
_EXCHANGES = {
    BINANCE: Binance,
    BINANCE_US: BinanceUS,
    BINANCE_FUTURES: BinanceFutures,
    BINANCE_DELIVERY: BinanceDelivery,
    BITCOINCOM: BitcoinCom,
    BITFINEX: Bitfinex,
    BITFLYER: Bitflyer,
    BITMAX: Bitmax,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    BITTREX: Bittrex,
    BLOCKCHAIN: Blockchain,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    COINGECKO: Coingecko,
    DERIBIT: Deribit,
    EXX_str: EXX,
    FTX_str: FTX,
    FTX_US: FTXUS,
    GEMINI: Gemini,
    HITBTC: HitBTC,
    HUOBI_DM: HuobiDM,
    HUOBI_SWAP: HuobiSwap,
    HUOBI: Huobi,
    KRAKEN_FUTURES: KrakenFutures,
    KRAKEN: Kraken,
    OKCOIN: OKCoin,
    OKEX: OKEx,
    POLONIEX: Poloniex,
    UPBIT: Upbit,
    GATEIO: Gateio,
    PROBIT: Probit,
    WHALE_ALERT: WhaleAlert
}


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
    def __init__(self, retries=10, timeout_interval=10, log_messages_on_error=False, raw_message_capture=None, config=None, exception_ignore: Optional[List[Exception]] = None):
        """
        retries: int
            number of times the connection will be retried (in the event of a disconnect or other failure)
        timeout_interval: int
            number of seconds between checks to see if a feed has timed out
        log_messages_on_error: boolean
            if true, log the message from the exchange on exceptions
        raw_message_capture: callback
            if defined, callback to save/process/handle raw message (primarily for debugging purposes)
        config: str, dict or None
            if str, absolute path (including file name) of the config file. If not provided, config can also be a dictionary of values, or
            can be None, which will default options. See docs/config.md for more information.
        exception_ignore: list, or None
            an optional list of exceptions that cryptofeed should ignore (i.e. not handle). These will need to be handled
            by a user-defined exception handler (provided to run run method) or the exception will kill the task (but not the feedhandler).
        """
        self.feeds = []
        self.retries = (retries + 1) if retries >= 0 else -1
        self.timeout = {}
        self.last_msg = defaultdict(lambda: None)
        self.timeout_interval = timeout_interval
        self.log_messages_on_error = log_messages_on_error
        self.raw_message_capture = raw_message_capture
        self.config = Config(config=config)
        if exception_ignore is not None and not isinstance(exception_ignore, list):
            raise ValueError("exception_ignore must be a list of Exceptions or None")
        self.exceptions = exception_ignore

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

    def add_feed(self, feed, timeout=120, **kwargs):
        """
        feed: str or class
            the feed (exchange) to add to the handler
        timeout: int
            number of seconds without a message before the feed is considered
            to be timed out. The connection will be closed, and if retries
            have not been exhausted, the connection will be reestablished.
            If set to -1, no timeout will occur.
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        if isinstance(feed, str):
            if feed in _EXCHANGES:
                self.feeds.append((_EXCHANGES[feed](config=self.config, **kwargs), timeout))
            else:
                raise ValueError("Invalid feed specified")
        else:
            self.feeds.append((feed, timeout))

    def add_feed_running(self, feed, loop=None, timeout=120, **kwargs):
        """
        Add and start a new feed to a running instance of cryptofeed

        feed: str or class
            the feed (exchange) to add to the handler
        loop: None, or EventLoop
            the loop on which to add the tasks
        timeout: int
            number of seconds without a message before the feed is considered
            to be timed out. The connection will be closed, and if retries
            have not been exhausted, the connection will be reestablished.
            If set to -1, no timeout will occur.
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        self.add_feed(feed, timeout=timeout, *kwargs)

        if loop is None:
            loop = asyncio.get_event_loop()

        f, timeout = self.feeds[-1]

        for conn, sub, handler in f.connect():
            if self.raw_message_capture:
                conn.set_raw_data_callback(self.raw_message_capture)
                self.raw_message_capture.set_header(conn.uuid, json.dumps(f._feed_config))
            self.timeout[conn.uuid] = timeout
            feed.start(loop)
            loop.create_task(self._connect(conn, sub, handler))

    def add_nbbo(self, feeds, symbols, callback, timeout=120):
        """
        feeds: list of feed classes
            list of feeds (exchanges) that comprises the NBBO
        symbols: list str
            the trading symbols
        callback: function pointer
            the callback to be invoked when a new tick is calculated for the NBBO
        timeout: int
            seconds without a message before a connection will be considered dead and reestablished.
            See `add_feed`
        """
        cb = NBBO(callback, symbols)
        for feed in feeds:
            self.add_feed(feed(channels=[L2_BOOK], symbols=symbols, callbacks={L2_BOOK: cb}), timeout=timeout)

    def run(self, start_loop: bool = True, install_signal_handlers: bool = True, exception_handler = None):
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
            txt = f'FH: No feed specified. Please specify at least one feed among {list(_EXCHANGES.keys())}'
            LOG.critical(txt)
            raise ValueError(txt)

        loop = asyncio.get_event_loop()
        # Good to enable when debugging or without code change: export PYTHONASYNCIODEBUG=1)
        # loop.set_debug(True)

        if install_signal_handlers:
            setup_signal_handlers(loop)

        for feed, timeout in self.feeds:
            for conn, sub, handler in feed.connect():
                if self.raw_message_capture:
                    self.raw_message_capture.set_header(conn.uuid, json.dumps(feed._feed_config))
                    conn.set_raw_data_callback(self.raw_message_capture)
                loop.create_task(self._connect(conn, sub, handler))
                self.timeout[conn.uuid] = timeout
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

        LOG.info('FH: flag retries=0 to stop the tasks running the connection handlers')
        self.retries = 0

        LOG.info('FH: create the tasks to properly shutdown the backends (to flush the local cache)')
        shutdown_tasks = []
        for feed, _ in self.feeds:
            task = loop.create_task(feed.shutdown())
            try:
                task.set_name(f'shutdown_feed_{feed.id}')
            except AttributeError:
                # set_name only in 3.8+
                pass
            shutdown_tasks.append(task)
        if self.raw_message_capture:
            self.raw_message_capture.stop()

        LOG.info('FH: wait %s backend tasks until termination', len(shutdown_tasks))
        loop.run_until_complete(asyncio.gather(*shutdown_tasks))

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

    async def _watch(self, connection):
        if self.timeout[connection.uuid] == -1:
            return

        while connection.open:
            if self.last_msg[connection.uuid]:
                if time() - self.last_msg[connection.uuid] > self.timeout[connection.uuid]:
                    LOG.warning("%s: received no messages within timeout, restarting connection", connection.uuid)
                    await connection.close()
                    break
            await asyncio.sleep(self.timeout_interval)

    async def _connect(self, conn, subscribe, handler):
        """
        Connect to exchange and subscribe
        """
        retries = 0
        rate_limited = 1
        delay = conn.delay
        while retries < self.retries or self.retries == -1:
            self.last_msg[conn.uuid] = None
            try:
                async with conn.connect() as connection:
                    asyncio.ensure_future(self._watch(connection))
                    # connection was successful, reset retry count and delay
                    retries = 0
                    rate_limited = 0
                    delay = conn.delay
                    await subscribe(connection)
                    await self._handler(connection, handler)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error) as e:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", conn.uuid, str(e))
                            raise
                LOG.warning("%s: encountered connection issue %s - reconnecting in %.1f seconds...", conn.uuid, str(e), delay, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2
            except InvalidStatusCode as e:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", conn.uuid, str(e))
                            raise
                if e.status_code == 429:
                    LOG.warning("%s: Rate Limited - waiting %d seconds to reconnect", conn.uuid, rate_limited * 60)
                    await asyncio.sleep(rate_limited * 60)
                    rate_limited += 1
                else:
                    LOG.warning("%s: encountered connection issue %s - reconnecting in %.1f seconds...", conn.uuid, str(e), delay, exc_info=True)
                    await asyncio.sleep(delay)
                    retries += 1
                    delay *= 2
            except Exception:
                if self.exceptions:
                    for ex in self.exceptions:
                        if isinstance(e, ex):
                            LOG.warning("%s: encountered exception %s, which is on the ignore list. Raising", conn.uuid, str(e))
                            raise
                LOG.error("%s: encountered an exception, reconnecting in %.1f seconds", conn.uuid, delay, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        if self.retries == 0:
            LOG.info('%s: terminate the connection handler because self.retries=0', conn.uuid)
        else:
            LOG.error('%s: failed to reconnect after %d retries - exiting', conn.uuid, retries)
            raise ExhaustedRetries()

    async def _handler(self, connection, handler):
        try:
            async for message in connection.read():
                if self.retries == 0:
                    return
                self.last_msg[connection.uuid] = time()
                await handler(message, connection, self.last_msg[connection.uuid])
        except Exception:
            if self.retries == 0:
                return
            if self.log_messages_on_error:
                if connection.uuid in {HUOBI, HUOBI_DM}:
                    message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                elif connection.uuid in {OKCOIN, OKEX}:
                    message = zlib.decompress(message, -15)
                LOG.error("%s: error handling message %s", connection.uuid, message)
            # exception will be logged with traceback when connection handler
            # retries the connection
            raise
