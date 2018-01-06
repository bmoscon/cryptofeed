'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import websockets

from .nbbo import NBBO


class FeedHandler(object):
    def __init__(self):
        self.feeds = []

    def add_feed(self, feed):
        self.feeds.append(feed)

    def add_nbbo(self, feeds, pairs, callback):
        for pair in pairs:
            cb = NBBO(callback, pair)
            for feed in feeds:
                self.add_feed(feed(channels=['ticker'], pairs=pairs, callbacks={'ticker': cb}))

    def run(self):
        if len(self.feeds) == 0:
            raise ValueError("No feeds specified")

        try:
            asyncio.get_event_loop().run_until_complete(self._run())
        except KeyboardInterrupt:
            pass

    def _run(self):
        feeds = [asyncio.ensure_future(self._connect(feed)) for feed in self.feeds]
        _, _ = yield from asyncio.wait(feeds)

    async def _connect(self, feed):
        async with websockets.connect(feed.address) as websocket:
            await feed.subscribe(websocket)
            await self._handler(websocket, feed.message_handler)

    async def _handler(self, websocket, handler):
        async for message in websocket:
            await handler(message)
