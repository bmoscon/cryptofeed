'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import zlib
from collections import defaultdict
from copy import deepcopy
from socket import error as socket_error
from time import time

import websockets
from websockets import ConnectionClosed

from cryptofeed.defines import (BINANCE, BINANCE_FUTURES, BINANCE_JERSEY, BINANCE_US, BITCOINCOM, BITFINEX,
                                BITMAX, BITMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, COINBASE, COINBENE, DERIBIT)
from cryptofeed.defines import EXX as EXX_str
from cryptofeed.defines import FTX as FTX_str
from cryptofeed.defines import (FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP, KRAKEN,
                                KRAKEN_FUTURES, L2_BOOK, OKCOIN, OKEX, POLONIEX, UPBIT)
from cryptofeed.exceptions import ExhaustedRetries
from cryptofeed.exchange.blockchain import Blockchain
from cryptofeed.exchanges import *
from cryptofeed.feed import RestFeed
from cryptofeed.log import get_logger
from cryptofeed.nbbo import NBBO


LOG = get_logger('feedhandler', 'feedhandler.log')


# Maps string name to class name for use with config
_EXCHANGES = {
    BINANCE: Binance,
    BINANCE_US: BinanceUS,
    BINANCE_JERSEY: BinanceJersey,
    BINANCE_FUTURES: BinanceFutures,
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
    GATEIO: Gateio
}


class FeedHandler:
    def __init__(self, retries=10, timeout_interval=10, log_messages_on_error=False, raw_message_capture=None, handler_enabled=True):
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
        """
        self.feeds = []
        self.retries = retries
        self.timeout = {}
        self.last_msg = {}
        self.timeout_interval = timeout_interval
        self.log_messages_on_error = log_messages_on_error
        self.raw_message_capture = raw_message_capture
        self.handler_enabled = handler_enabled

    def add_feed(self, feed, timeout=120, **kwargs):
        """
        feed: str or class
            the feed (exchange) to add to the handler
        timeout: int
            number of seconds without a message before the feed is considered
            to be timed out. The connection will be closed, and if retries
            have not been exhausted, the connection will be restablished.
            If set to -1, no timeout will occur.
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
                    self.last_msg[feed.uuid] = None
                    self.timeout[feed.uuid] = timeout
            else:
                raise ValueError("Invalid feed specified")
        else:
            if isinstance(feed, Bitmax):
                self._do_bitmax_subscribe(feed, timeout)
            else:
                self.feeds.append(feed)
                self.last_msg[feed.uuid] = None
                self.timeout[feed.uuid] = timeout

    def add_nbbo(self, feeds, pairs, callback, timeout=120):
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

        try:
            loop = asyncio.get_event_loop()
            # Good to enable when debugging
            # loop.set_debug(True)

            for feed in self.feeds:
                if isinstance(feed, RestFeed):
                    loop.create_task(self._rest_connect(feed))
                else:
                    loop.create_task(self._connect(feed))
            if start_loop:
                loop.run_forever()
        except KeyboardInterrupt:
            LOG.info("Keyboard Interrupt received - shutting down")
        except Exception:
            LOG.error("Unhandled exception", exc_info=True)

    async def _watch(self, feed_id, websocket):
        if self.timeout[feed_id] == -1:
            return

        while websocket.open:
            if self.last_msg[feed_id]:
                if time() - self.last_msg[feed_id] > self.timeout[feed_id]:
                    LOG.warning("%s: received no messages within timeout, restarting connection", feed_id)
                    await websocket.close()
                    break
            await asyncio.sleep(self.timeout_interval)

    async def _rest_connect(self, feed):
        """
        Connect to REST feed
        """
        retries = 0
        delay = 1
        while retries <= self.retries or self.retries == -1:
            await feed.subscribe()
            try:
                while True:
                    await feed.message_handler()
            except Exception:
                LOG.error("%s: encountered an exception, reconnecting", feed.id, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        LOG.error("%s: failed to reconnect after %d retries - exiting", feed.id, retries)
        raise ExhaustedRetries()

    async def _connect(self, feed):
        """
        Connect to websocket feeds
        """
        retries = 0
        delay = 1
        while retries <= self.retries or self.retries == -1:
            self.last_msg[feed.uuid] = None
            try:
                # Coinbase frequently will not respond to pings within the ping interval, so
                # disable the interval in favor of the internal watcher, which will
                # close the connection and reconnect in the event that no message from the exchange
                # has been received (as opposed to a missing ping)
                async with websockets.connect(feed.address, ping_interval=30, ping_timeout=None,
                        max_size=2**23, max_queue=None, origin=feed.origin) as websocket:
                    asyncio.ensure_future(self._watch(feed.uuid, websocket))
                    # connection was successful, reset retry count and delay
                    retries = 0
                    delay = 1
                    await feed.subscribe(websocket)
                    await self._handler(websocket, feed.message_handler, feed.uuid)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError, socket_error) as e:
                LOG.warning("%s: encountered connection issue %s - reconnecting...", feed.id, str(e), exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2
            except Exception:
                LOG.error("%s: encountered an exception, reconnecting", feed.id, exc_info=True)
                await asyncio.sleep(delay)
                retries += 1
                delay *= 2

        LOG.error("%s: failed to reconnect after %d retries - exiting", feed.id, retries)
        raise ExhaustedRetries()

    async def _handler(self, websocket, handler, feed_id):
        try:
            if self.raw_message_capture and self.handler_enabled:
                async for message in websocket:
                    self.last_msg[feed_id] = time()
                    await self.raw_message_capture(message, self.last_msg[feed_id], feed_id)
                    await handler(message, self.last_msg[feed_id])
            elif self.raw_message_capture:
                async for message in websocket:
                    self.last_msg[feed_id] = time()
                    await self.raw_message_capture(message, self.last_msg[feed_id], feed_id)
            else:
                async for message in websocket:
                    self.last_msg[feed_id] = time()
                    await handler(message, self.last_msg[feed_id])
        except Exception:
            if self.log_messages_on_error:
                if feed_id in {HUOBI, HUOBI_DM}:
                    message = zlib.decompress(message, 16 + zlib.MAX_WBITS)
                elif feed_id in {OKCOIN, OKEX}:
                    message = zlib.decompress(message, -15)
                LOG.error("%s: error handling message %s", feed_id, message)
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
                self.last_msg[feed.uuid] = None
                self.timeout[feed.uuid] = timeout
        else:
            if 'pairs' in kwargs:
                pairs = kwargs.pop('pairs')
            elif hasattr(feed, 'pairs'):
                pairs = feed.pairs

            for pair in pairs:
                feed = Bitmax(pairs=[pair], callbacks=callbacks, **kwargs)
                self.feeds.append(feed)
                self.last_msg[feed.uuid] = None
                self.timeout[feed.uuid] = timeout
