'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
import functools
import logging
import signal
from signal import SIGABRT, SIGINT, SIGTERM
import sys
from typing import Callable, Iterable, List, Optional, Tuple, Union

try:
    # unix / macos only
    from signal import SIGHUP
    SIGNALS = (SIGABRT, SIGINT, SIGTERM, SIGHUP)
except ImportError:
    SIGNALS = (SIGABRT, SIGINT, SIGTERM)


from cryptofeed.config import Config
from cryptofeed.connection import AsyncConnection, HTTPAsyncConn, WSAsyncConn
from cryptofeed.defines import (BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BINANCE_US, BITCOINCOM, BITFINEX, BITFLYER,
                                BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, COINBASE, COINGECKO,
                                DERIBIT, FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN, KRAKEN_FUTURES, OKCOIN, OKEX, POLONIEX, PROBIT, UPBIT, WHALE_ALERT)
from cryptofeed.defines import EXX as EXX_str
from cryptofeed.defines import FTX as FTX_str
from cryptofeed.defines import L2_BOOK
from cryptofeed.exchanges import *
from cryptofeed.feed import Feed
from cryptofeed.log import get_logger
from cryptofeed.nbbo import NBBO
from cryptofeed.providers import *
from cryptofeed.runner import Runner


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
    def __init__(self, retries=10, timeout_interval=10, log_messages_on_error=False, raw_message_capture=None, handler_enabled=True, config=None):
        """
        retries: int
            number of times the connection will be retried (in the event of a disconnect or other failure)
        timeout_interval: int
            number of seconds between checks to see if a feed has timed out
        log_messages_on_error: boolean
            if true, log the message from the exchange on exceptions
        raw_message_capture: callback
            if defined, callback to save/process/handle raw message (primarily for debugging purposes)
        handler_enabled: boolean
            run message runners (and any registered callbacks) when raw message capture is enabled
        config: str, dict or None
            if str, absolute path (including file name) of the config file. If not provided, config can also be a dictionary of values, or
            can be None, which will default options. See docs/config.md for more information.
        """
        self.feeds: List[Tuple[Feed, List[Runner]]] = []
        self.retries = retries
        self.timeout_interval = timeout_interval
        self.log_messages_on_error = log_messages_on_error
        self.raw_message_capture = raw_message_capture  # TODO: create/append callbacks to do raw_message_capture
        self.handler_enabled = handler_enabled
        self.config = Config(config=config)

        get_logger('feedhandler', self.config.log.filename, self.config.log.level)
        if self.config.log_msg:
            LOG.info(self.config.log_msg)

    def playback(self, feed, filenames):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._playback(feed, filenames))

    async def _playback(self, feed, filenames):
        counter = 0
        callbacks = defaultdict(int)

        class FakeWS(AsyncConnection):
            async def _open(self):
                self.socket = None
            async def send(self, *args, **kwargs):
                pass

        async def internal_cb(*args, **kwargs):
            callbacks[kwargs['cb_type']] += 1

        for cb_type, handler in feed.callbacks.items():
            f = functools.partial(internal_cb, cb_type=cb_type)
            handler.append(f)

        conn = FakeWS(conn_id='FAKE-CONN', ctx={})
        await feed.subscribe(conn)
        for filename in filenames if isinstance(filenames, list) else [filenames]:
            with open(filename, 'r') as fp:
                for line in fp:
                    timestamp, data = line.split(":", 1)
                    counter += 1
                    await feed.handle(data, timestamp, conn)
            return {'messages_processed': counter, 'callbacks': dict(callbacks)}

    def add_feed(self, feed: Union[str, Feed], timeout: float = None, **kwargs):
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
                feed = _EXCHANGES[feed](config=self.config, **kwargs)
            else:
                txt = f'FH: invalid feed {feed!r} must be one of: {list(_EXCHANGES.values())}'
                LOG.critical(txt)
                raise ValueError(txt)

        timeout = timeout if timeout is not None else self.timeout_interval
        max_retries = self.retries or 1  # Do not set zero because it flags the final shutdown
        runners = []
        for conn in self.create_connections(feed):
            runners.append(Runner(feed, conn, timeout, max_retries))

        if len(runners) == 0:
            txt = f'FH {feed.id}: Nothing to subscribe (no runner).'
            LOG.critical(txt)
            raise ValueError(txt)

        LOG.debug('FH %s: prepare feed with %s runners', feed.id, len(runners))
        self.feeds.append((feed, runners))

    @staticmethod
    def create_connections(feed: Feed) -> List[AsyncConnection]:
        if isinstance(feed.address, str):
            address: dict = {'': feed.address}
        elif isinstance(feed.address, dict):
            address: dict = feed.address
        else:
            err = f'FH {feed.id}: type of feed address must be str or dict but got {feed.address!r}'
            LOG.critical(err)
            raise TypeError(err)

        http_addr = {}
        for opt, addr in address.items():
            if addr[:2] == 'ws':
                LOG.debug('FH %s: prepare WS connection addr: %s', feed.id, addr)
                yield WSAsyncConn({opt: addr}, feed.id, feed.handle, **feed.ws_defaults)
            else:
                http_addr[opt] = addr  # collect all HTTP addresses to create one single HTTPAsyncConn

        if http_addr:
            addr_compute: Optional[Callable[[], Iterable[dict]]] = getattr(feed, 'addr_compute', None)  # used by HTTPAsyncConn.read()
            LOG.debug('FH %s: prepare HTTP connection with %s addresses and addr_compute=%s', feed.id, len(http_addr), addr_compute)
            yield HTTPAsyncConn(http_addr, feed.id, feed.SLEEP_TIME, addr_compute)

    def add_nbbo(self, feeds: list, symbols, callback, timeout: float = 120.0):
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

    def run(self, start_loop: bool = True, install_signal_handlers: bool = True):
        """
        start_loop: bool, default True
            if false, will not start the event loop. Also, will not
            use uvlib/uvloop if false, the caller will
            need to init uvloop if desired.
        install_signal_handlers: bool, default True
            if True, will install the signal handlers on the event loop. This
            can only be done from the main thread's loop, so if running cryptofeed on
            a child thread, this must be set to false, and setup_signal_handlers must
            be called from the main/parent thread's event loop
        """
        if len(self.feeds) == 0:
            txt = f'FH: No feed specified. Please specify at least one feed among {list(_EXCHANGES.keys())}'
            LOG.critical(txt)
            raise ValueError(txt)

        # The user managing the ASyncIO loop themselves sets start_loop=False => they decide to enable uvloop if they want to
        # therefore, the FeedHandler attempts to enable uvloop only when start_loop==True
        if start_loop:
            try:
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
                LOG.info('FH: uvloop activated')
            except Exception as why:  # ImportError
                LOG.info('FH: no uvloop because %r', why)

        loop = asyncio.get_event_loop()
        # Good to enable when debugging or without code change: export PYTHONASYNCIODEBUG=1)
        # loop.set_debug(True)

        if install_signal_handlers:
            setup_signal_handlers(loop)

        for feed, runners in self.feeds:
            for r in runners:
                LOG.debug('FH %s: The runner task is ready', r.id)
                task = loop.create_task(r.run(self.handler_enabled, self.raw_message_capture, self.log_messages_on_error))
                task.set_name(f'runner_{r.id}')

        if not start_loop:
            return

        try:
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

        LOG.info('FH: close WS connections and stop Runner loops')
        for feed, runners in self.feeds:
            for r in runners:
                task = loop.create_task(r.shutdown())
                task.set_name(f'stop_loop_{r.id}')

        LOG.info('FH: create the tasks to properly shutdown the backends (to flush the local cache)')
        shutdown_tasks = []
        for feed, runners in self.feeds:
            task = loop.create_task(feed.shutdown())
            task.set_name(f'shutdown_feed_{feed.id}')
            shutdown_tasks.append(task)

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
