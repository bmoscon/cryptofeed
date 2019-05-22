'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from time import time as time
from socket import error as socket_error
import zlib

import websockets
from websockets import ConnectionClosed

from cryptofeed.defines import L2_BOOK
from cryptofeed.log import get_logger
from cryptofeed.defines import GEMINI, HITBTC, BITFINEX, BITMEX, BITSTAMP, POLONIEX, COINBASE, KRAKEN, HUOBI, HUOBI_US, OKCOIN, OKEX, COINBENE
from cryptofeed.exchanges import Gemini, HitBTC, Bitfinex, Bitmex, Bitstamp, Poloniex, Coinbase, Kraken, OKCoin, OKEx, Coinbene, HuobiUS
from cryptofeed.nbbo import NBBO
from cryptofeed.feed import RestFeed


LOG = get_logger('feedhandler', 'feedhandler.log')


_EXCHANGES = {
    COINBASE: Coinbase,
    GEMINI: Gemini,
    HITBTC: HitBTC,
    POLONIEX: Poloniex,
    BITFINEX: Bitfinex,
    BITMEX: Bitmex,
    BITSTAMP: Bitstamp,
    KRAKEN: Kraken,
    HUOBI: HUOBI,
    HUOBI_US: HuobiUS,
    OKCOIN: OKCoin,
    OKEX: OKEx,
    COINBENE: Coinbene
}


class FeedHandler:
    def __init__(self, retries=10, timeout_interval=10):
        """
        retries: int
            number of times the connection will be retried (in the event of a disconnect or other failure)
        timeout_interval: int
            number of seconds between checks to see if a feed has timed out
        """
        self.feeds = []
        self.retries = retries
        self.timeout = {}
        self.last_msg = {}
        self.timeout_interval = timeout_interval

    def add_feed(self, feed, timeout=120, **kwargs):
        """
        feed: str or class
            the feed (exchange) to add to the handler
        timeout: int
            number of seconds without a message before the feed is considered
            to be timed out. The connection will be closed, and if retries
            have not been exhausted, the connection will be restablished
        kwargs: dict
            if a string is used for the feed, kwargs will be passed to the
            newly instantiated object
        """
        if isinstance(feed, str):
            if feed in _EXCHANGES:
                self.feeds.append(_EXCHANGES[feed](**kwargs))
                feed = _EXCHANGES[feed]
            else:
                raise ValueError("Invalid feed specified")
        else:
            self.feeds.append(feed)
        self.last_msg[feed.id] = None
        self.timeout[feed.id] = timeout

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
            if feed.id == 'GEMINI':
                for pair in pairs:
                    self.add_feed(feed(pairs=[pair], callbacks={L2_BOOK: cb}), timeout=timeout)
            else:
                self.add_feed(feed(channels=[L2_BOOK], pairs=pairs, callbacks={L2_BOOK: cb}), timeout=timeout)

    def run(self):
        if len(self.feeds) == 0:
            LOG.error('No feeds specified')
            raise ValueError("No feeds specified")

        try:
            loop = asyncio.get_event_loop()

            for feed in self.feeds:
                if isinstance(feed, RestFeed):
                    loop.create_task(self._rest_connect(feed))
                else:
                    loop.create_task(self._connect(feed))
            loop.run_forever()
        except KeyboardInterrupt:
            LOG.info("Keyboard Interrupt received - shutting down")
        except Exception:
            LOG.error("Unhandled exception", exc_info=True)

    async def _watch(self, feed_id, websocket):
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
        while retries <= self.retries:
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

    async def _connect(self, feed):
        """
        Connect to websocket feeds
        """
        retries = 0
        delay = 1
        while retries <= self.retries:
            self.last_msg[feed.id] = None
            try:
                # Coinbase frequently will not respond to pings within the ping interval, so
                # disable the interval in favor of the internal watcher, which will
                # close the connection and reconnect in the event that no message from the exchange
                # has been received (as opposed to a missing ping)
                async with websockets.connect(feed.address, ping_interval=30, ping_timeout=None) as websocket:
                    asyncio.ensure_future(self._watch(feed.id, websocket))
                    # connection was successful, reset retry count and delay
                    retries = 0
                    delay = 1
                    await feed.subscribe(websocket)
                    await self._handler(websocket, feed.message_handler, feed.id)
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

    async def _handler(self, websocket, handler, feed_id):
        async for message in websocket:
            self.last_msg[feed_id] = time()
            try:
                await handler(message)
            except Exception:
                if feed_id == HUOBI or feed_id == HUOBI_US:
                    message = zlib.decompress(message, 16+zlib.MAX_WBITS)
                elif feed_id == OKCOIN or feed_id == OKEX:
                    message = zlib.decompress(message, -15)
                LOG.error("%s: error handling message %s", feed_id, message)
                # exception will be logged with traceback when connection handler
                # retries the connection
                raise
