'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions 
associated with this software.
'''
import asyncio
import json

import websockets

from gdax import GDAX
from bitfinex import Bitfinex
from poloniex import Poloniex


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
            await handler(message)


if __name__ == '__main__':
    from callback import TickerCallback, TradeCallback, BookCallback
    def ticker(feed, pair, bid, ask):
        print('Feed: {} Pair: {} Bid: {} Ask: {}'.format(feed, pair, bid, ask))
    def trade(feed, pair, side, amount, price):
        print('Feed: {} Pair: {} side: {} Amount: {} Price: {}'.format(feed, pair, side, amount, price))
    def book(b):
        print('book bid size is {} ask size is {}'.format(len(b['BTC-USD']['bid']), len(b['BTC-USD']['ask'])))
    f = FeedHandler()
    f.add_feed(GDAX(pairs=['BTC-USD'], channels=['full'], callbacks={'book': BookCallback(book)}))
    #f.add_feed(GDAX(pairs=['BTC-USD'], channels=['matches'], callbacks={'trades': TradeCallback(trade)}))
    #f.add_feed(Bitfinex(pairs=['tBTCUSD'], channels=['ticker'], callbacks={'ticker': TickerCallback(p)}))
    #f.add_feed(Poloniex(channels=['USDT_BTC']))
    #f.add_feed(Poloniex(channels=['USDT_BTC']))
    f.run()
