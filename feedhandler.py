import asyncio
import json

import websockets

from gdax import GDAX
from bitfinex import Bitfinex


class FeedHandler(object):
    def __init__(self):
        self.feeds = []
    
    def add_feed(self, feed):
        self.feeds.append(feed)
    
    def run(self):
        asyncio.get_event_loop().run_until_complete(self._run())

    def _run(self):
        loop = asyncio.get_event_loop()
        feeds = [asyncio.ensure_future(self._connect(feed)) for feed in self.feeds]
        done, pending = yield from asyncio.wait(feeds)
    
    async def _connect(self, feed):
        async with websockets.connect(feed.address) as websocket:
            await feed.subscribe(websocket)
            await self._handler(websocket, feed.message_handler)

    async def _handler(self, websocket, handler):
        async for message in websocket:
            handler(message)


if __name__ == '__main__':
    f = FeedHandler()
    #f.add_feed(GDAX(pairs=['BTC-USD'], channels=['ticker']))
    f.add_feed(Bitfinex(pairs=['tBTCUSD'], channels=['trades', 'ticker']))
    f.run()
