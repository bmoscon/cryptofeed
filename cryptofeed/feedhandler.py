'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from signal import SIGTERM
import zlib
from collections import defaultdict
from copy import deepcopy
from socket import error as socket_error
from time import time
import functools

import websockets
from websockets import ConnectionClosed

from cryptofeed.config import Config
from cryptofeed.defines import (BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BINANCE_US, BITCOINCOM, BITFINEX,
                                BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT,
                                COINBASE, COINBENE, COINGECKO, DERIBIT,
                                FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN, KRAKEN_FUTURES, OKCOIN, OKEX, POLONIEX, PROBIT, UPBIT, WHALE_ALERT)
from cryptofeed.defines import EXX as EXX_str
from cryptofeed.defines import FTX as FTX_str
from cryptofeed.defines import L2_BOOK
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.exchanges import *
from cryptofeed.providers import *
from cryptofeed.feed import RestFeed, WebsocketFeed, Feed
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
    BITMAX: Bitmax,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    BITTREX: Bittrex,
    BLOCKCHAIN: Blockchain,
    BYBIT: Bybit,
    COINBASE: Coinbase,
    COINBENE: Coinbene,
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
            run message handlers (and any registered callbacks) when raw message capture is enabled
        config: str
            absolute path (including file name) of the config file. If not provided env var checked first, then local config.yaml
        """
        self.feeds = []
        self.max_retries = retries
        self.timeout: Dict[str, int] = {}  # in seconds
        self.msg_count: Dict[str, int] = {}  # count number of received messages since last watchdog check
        self.timeout_interval = timeout_interval
        self.log_messages_on_error = log_messages_on_error
        self.raw_message_capture = raw_message_capture
        self.handler_enabled = handler_enabled
        self.config = Config(file_name=config)

        lfile = 'feedhandler.log' if not self.config or not self.config.log.filename else self.config.log.filename
        level = logging.WARNING if not self.config or not self.config.log.level else self.config.log.level
        get_logger('feedhandler', lfile, level)

    def playback(self, feed, filenames):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self._playback(feed, filenames))

    async def _playback(self, feed, filenames):
        counter = 0
        callbacks = defaultdict(int)

        class FakeWS:
            async def send(self, *args, **kwargs):
                pass

        async def internal_cb(*args, **kwargs):
            callbacks[kwargs['cb_type']] += 1

        for cb_type, handler in feed.callbacks.items():
            f = functools.partial(internal_cb, cb_type=cb_type)
            handler.append(f)

        await feed.subscribe(FakeWS())

        for filename in filenames if isinstance(filenames, list) else [filenames]:
            with open(filename, 'r') as fp:
                for line in fp:
                    timestamp, message = line.split(":", 1)
                    counter += 1
                    await feed.message_handler(message, timestamp)
            return {'messages_processed': counter, 'callbacks': dict(callbacks)}

    def add_feed(self, feed: Union[str,Feed], timeout=300, **kwargs):
        """
        feed: str or class
            the feed (exchange) to add to the handler
        timeout: int
            number of seconds without a message before the feed is considered
            to be timed out. The connection will be closed, and if retries
            have not been exhausted, the connection will be reestablished.
            If set to negative value, no timeout will occur.
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        if isinstance(feed, str):
            if feed in _EXCHANGES:
                if feed == BITMAX:
                    self._do_bitmax_subscribe(feed, timeout, **kwargs)
                else:
                    self.feeds.append(_EXCHANGES[feed](**kwargs))
                    feed = self.feeds[-1]
                    self.msg_count[feed.uuid] = -1
                    self.timeout[feed.uuid] = timeout
            else:
                raise ValueError("Invalid feed specified")
        else:
            if isinstance(feed, Bitmax):
                self._do_bitmax_subscribe(feed, timeout)
            else:
                self.feeds.append(feed)
                self.msg_count[feed.uuid] = -1
                self.timeout[feed.uuid] = timeout

    def add_nbbo(self, feeds: list, pairs, callback, timeout=120):
        """
        feeds: list of feed classes
            list of feeds (exchanges) that comprises the NBBO
        pairs: list str
            the trading pairs
        callback: function pointer
            the callback to be invoked when a new tick is calculated for the NBBO
        timeout: int
            seconds without a message before a connection will be considered dead and reestablished.
            See `add_feed`
        """
        cb = NBBO(callback, pairs)
        for feed in feeds:
            self.add_feed(feed(channels=[L2_BOOK], pairs=pairs, callbacks={L2_BOOK: cb}), timeout=timeout)

    def run(self, start_loop=True):
        if len(self.feeds) == 0:
            LOG.error('No feeds specified')
            raise ValueError("No feeds specified")

        loop = asyncio.get_event_loop()
        # Good to enable when debugging
        # loop.set_debug(True)

        def handle_stop_signals():
            raise SystemExit

        for signal in [SIGTERM]:
            loop.add_signal_handler(signal, handle_stop_signals)

        for feed in self.feeds:
            if isinstance(feed, RestFeed):
                loop.create_task(self._rest_connect(feed))
            else:
                loop.create_task(self._connect(feed))

        if start_loop:
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                LOG.info("FH: Keyboard Interrupt received - shutting down")
            except SystemExit:
                LOG.info("FH: System Exit received - shutting down")
            except Exception as why:
                LOG.exception("FH Unhandled %r", why)
            finally:
                for feed in self.feeds:
                    feed.max_retries = 0  # Stop infinite loop
                    LOG.info("FH %s %s: Stopping", feed.id, feed.uuid)
                    loop.run_until_complete(feed.stop())

    async def _watch(self, feed: WebsocketFeed, websocket: websockets.WebSocketClientProtocol):
        if self.timeout[feed.uuid] <= 0:
            return

        LOG.info("FH %s %s: Initial WS timeout = %0.1f seconds", feed.id, feed.uuid, self.timeout[feed.uuid])
        timeout = last_log_sleep = self.timeout[feed.uuid]
        self.msg_count[feed.uuid] = -1

        while websocket.open:
            if self.msg_count[feed.uuid] == 0:
                self.timeout[feed.uuid] = 30 + 2 * timeout  # Increase for next watch
                LOG.warning("FH %s %s: No msg within %0.1f seconds => Reconnect websocket. Next timeout = %.1f",
                            feed.id, feed.uuid, timeout, self.timeout[feed.uuid])
                try:
                    await websocket.close()
                except Exception as why:
                    LOG.warning("FH %s %s: Cannot close websocket because %r", feed.id, feed.uuid, why)
                return

            # Ideal timeout is waiting between 10 messages (low frequency) to 100 messages (high frequency)
            if self.msg_count[feed.uuid] > 0:
                frequency = self.msg_count[feed.uuid] / timeout
                sleep_target = 10/frequency + 20  # Wait at least 20 seconds
                new_timeout = (4*timeout + sleep_target) / 5  # Average 80% / 20%.
                if abs(last_log_sleep - new_timeout) > 30:  # Reduce amount of logs
                    LOG.info("FH %s %s: Adaptive WS timeout = %0.1f -> %0.1f -> %0.1f seconds (%.3f msg/sec -> target %0.1f sec)",
                             feed.id, feed.uuid, last_log_sleep, timeout, new_timeout, self.msg_count[feed.uuid]/timeout, sleep_target)
                    last_log_sleep = new_timeout
                timeout = new_timeout

            self.msg_count[feed.uuid] = 0
            await asyncio.sleep(timeout)

        LOG.info("FH %s %s: WS closed, Stop watching. count=%s", feed.id, feed.uuid, self.msg_count[feed.uuid])

    async def _rest_connect(self, feed):
        """
        Connect to REST feed
        """
        retries = 0
        delay = 2 * feed.sleep_time if feed.sleep_time else 1
        while retries <= self.max_retries or self.max_retries == -1:
            LOG.info("FH %s: Subscribe", feed.id)
            await feed.subscribe()
            LOG.info("FH %s %s: Start REST event loop", feed.id, feed.uuid)
            try:
                while self.max_retries:
                    await feed.rest_handler()
                    # connection was successful, reset retry count and delay
                    retries = 0
                    delay = 2 * feed.sleep_time if feed.sleep_time else 1
            except Exception as why:
                LOG.warning("FH %s: While handling REST: %r => Reconnecting in %.1f seconds", feed.id, why, delay, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        if self.max_retries:
            LOG.error("FH %s: Failed to reconnect REST after %d retries => End of task", feed.id, retries, stack_info=True)
        else:
            LOG.info("FH %s: End of task", feed.id)
        raise ExhaustedRetries()

    async def _connect(self, feed: WebsocketFeed):
        """
        Connect to websocket feeds
        """
        LOG.info("FH %s %s: Start Websocket connection", feed.id, feed.uuid)
        retries = 1
        delay = 1
        while retries < self.max_retries or self.max_retries == -1:
            LOG.info("FH %s %s: retries=%s < max=%s delay=%.1f websockets.connect(%.200s)",
                     feed.id, feed.uuid, retries, self.max_retries, delay, feed.address)
            try:
                # Coinbase frequently will not respond to pings within the ping interval, so
                # disable the interval (ping_timeout=None) in favor of the internal watcher,
                # which will close the connection and reconnect in the event that no message
                # from the exchange has been received (as opposed to a missing ping).
                #
                # Set ping_interval=15 because HUOBI close the websocket after 16 seconds with message
                #     ping check expired, session: 0228d8f7-ec75-4352-b043-c6bbd1a61542
                #
                # address can be None for binance futures when only open interest is configured
                # because that data is collected over a periodic REST polling task
                if feed.address is None:
                    await feed.subscribe(None)
                    return

                async with websockets.connect(feed.address, ping_interval=15, ping_timeout=None,
                                              max_size=2**23, max_queue=None, origin=feed.origin) as websocket:
                    asyncio.ensure_future(self._watch(feed, websocket))
                    # connection was successful, reset retry count and delay
                    retries = 1
                    delay = 2

                    LOG.info("FH %s %s: Subscribe", feed.id, feed.uuid)
                    subscribed = await feed.subscribe(websocket)
                    if not subscribed:
                        LOG.info("FH %s %s: Close websocket because do not wait for any response", feed.id, feed.uuid)
                        await websocket.close()
                        return

                    LOG.info("FH %s %s: Handle websocket messages", feed.id, feed.uuid)
                    await self._handler(feed, websocket)
            except Exception as why:  # ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error ...
                LOG.warning("FH %s %s: retries=%r max=%r Reconnecting in %.1f seconds... %r",
                            feed.id, feed.uuid, retries, self.max_retries, delay, why, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        if self.max_retries:
            LOG.error("FH %s %s: Failed to reconnect after %s retries > max=%s => End of task",
                      feed.id, feed.uuid, retries, self.max_retries, stack_info=True)
        else:
            LOG.info("FH %s %s: End of task", feed.id, feed.uuid)
        raise ExhaustedRetries()

    async def _handler(self, feed: WebsocketFeed, websocket: websockets.WebSocketClientProtocol):
        message = None
        try:
            async for message in websocket:
                receipt_ns = time.time_ns()
                self.msg_count[feed.uuid] += 1
                try:
                    if self.raw_message_capture:
                        await self.raw_message_capture(message, receipt_ns, feed.uuid)
                    if self.handler_enabled:
                        await feed.message_handler(message, receipt_ns)
                    if self.max_retries == 0:
                        LOG.info("FH %s %s: max_retries==0 => stop _connect()", feed.id, feed.uuid)
                        return
                except Exception as why:
                    if self.log_messages_on_error:
                        if feed.id in {HUOBI, HUOBI_DM, HUOBI_SWAP}:
                            message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                        elif feed.id in {OKCOIN, OKEX}:
                            message = zlib.decompress(message, -15)
                        LOG.warning("FH %s %s: websocket message: %.500r (limited to 500 characters)", feed.id, feed.uuid, message)
                    LOG.warning("FH %s %s: Processing websocket but %r", feed.id, feed.uuid, why, exc_info=True)
                    if isinstance(why, aiohttp.client_exceptions.ClientResponseError):
                        # BINANCE sends this error
                        # if we retry => BINANCE bans the IP for a couple of hours
                        if 'too many requests' in str(why).lower():
                            LOG.critical("FH %s %s: %r => Stop FeedHandler", feed.id, feed.uuid, why)
                            self.max_retries = 0
                            raise  # Better to stop the Feed Handler
        except Exception as why:
            LOG.warning("FH %s %s: Websocket error: %r", feed.id, feed.uuid, why)
            if message and self.log_messages_on_error:
                if feed.id in {HUOBI, HUOBI_DM, HUOBI_SWAP}:
                    message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                elif feed.id in {OKCOIN, OKEX}:
                    message = zlib.decompress(message, -15)
                LOG.warning("FH %s %s: message: %.500r (limited to 500 characters)", feed.id, feed.uuid, message)
            # exception will be logged with traceback when connection handler
            # retries the connection
            raise

    def _do_bitmax_subscribe(self, feed, timeout: int, **kwargs):
        """
        Bitmax is a special case, a separate websocket is needed for each symbol,
        and each connection receives all data for that symbol. We allow the user
        to configure Bitmax like they would any other exchange and parse out the
        relevant information to create a separate feed object per symbol.
        """
        config = {}
        pairs = []

        # Need to handle the two configuration cases - Feed object and Feed Name with config dict
        if 'config' in kwargs:
            config = kwargs.pop('config')
        elif hasattr(feed, 'config'):
            config = feed.config

        if isinstance(feed, str):
            callbacks = kwargs.pop('callbacks')
        else:
            callbacks = feed.callbacks

        if config:
            new_config = defaultdict(list)
            for cb, symbols in config.items():
                for symbol in symbols:
                    new_config[symbol].append(cb)

            for symbol, cbs in new_config.items():
                cb = {cb: deepcopy(callbacks[cb]) for cb in cbs}
                feed = Bitmax(pairs=[symbol], callbacks=cb, **kwargs)
                self.feeds.append(feed)
                self.msg_count[feed.uuid] = -1
                self.timeout[feed.uuid] = timeout
        else:
            if 'pairs' in kwargs:
                pairs = kwargs.pop('pairs')
            elif hasattr(feed, 'pairs'):
                pairs = feed.pairs

            for pair in pairs:
                feed = Bitmax(pairs=[pair], callbacks=callbacks, **kwargs)
                self.feeds.append(feed)
                self.msg_count[feed.uuid] = -1
                self.timeout[feed.uuid] = timeout
