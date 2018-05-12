'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging

import websockets
from websockets import ConnectionClosed

from cryptofeed.defines import TICKER
from cryptofeed import Gemini
from .nbbo import NBBO


FORMAT = '%(asctime)-15s : %(levelname)s : %(message)s'
logging.basicConfig(level=logging.WARNING,
                    format=FORMAT,
                    handlers=[logging.FileHandler('feedhandler.log'),
                              logging.StreamHandler()])

LOG = logging.getLogger('feedhandler')


class FeedHandler(object):
    def __init__(self, retries=10):
        self.feeds = []
        self.retries = retries

    def add_feed(self, feed):
        self.feeds.append(feed)

    def add_nbbo(self, feeds, pairs, callback):
        cb = NBBO(callback, pairs)
        for feed in feeds:
            self.add_feed(feed(channels=[TICKER], pairs=pairs, callbacks={TICKER: cb}))

    def run(self):
        if self.feeds == []:
            LOG.error('No feeds specified')
            raise ValueError("No feeds specified")

        try:
            asyncio.get_event_loop().run_until_complete(self._run())
        except KeyboardInterrupt:
            LOG.info("Keyboard Interrupt received - shutting down")
            pass
        except Exception as e:
            LOG.error("Unhandled exception: %s", str(e))

    def _run(self):
        feeds = [asyncio.ensure_future(self._connect(feed)) for feed in self.feeds]
        _, _ = yield from asyncio.wait(feeds)

    async def _connect(self, feed):
        retries = 0
        delay = 1.0
        while retries <= self.retries:
            try:
                async with websockets.connect(feed.address) as websocket:
                    await feed.subscribe(websocket)
                    await self._handler(websocket, feed.message_handler)
            except (ConnectionClosed, ConnectionAbortedError, ConnectionResetError) as e:
                LOG.warning("Feed {} encountered connection issue {} - reconnecting...".format(feed.id, str(e)))
                await asyncio.sleep(delay)
                retries += 1
                delay = delay * 2
        LOG.error("Feed {} failed to reconnect after {} retries - exiting".format(feed.id, retries))

    async def _handler(self, websocket, handler):
        async for message in websocket:
            await handler(message)
