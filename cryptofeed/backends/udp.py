'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import asyncio
import json

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert


LOG = logging.getLogger('feedhandler')


class UDPProtocol:
    def __init__(self, loop):
        self.loop = loop
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
       pass

    def error_received(self, exc):
        LOG.error('UDP backend received exception: %s', exc)
        self.transport.close()
        self.transport = None

    def connection_lost(self, exc):
        LOG.error('UDP backend connection lost: %s', exc)
        self.transport.close()
        self.transport = None


class UDPCallback:
    def __init__(self, host='127.0.0.1', port=5555, **kwargs):
        self.transport = None
        self.protocol = None
        self.host = host
        self.port = port

    async def connect(self):
        if not self.transport:
            loop = asyncio.get_event_loop()
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPProtocol(loop), remote_addr=(self.host, self.port))


class TradeUDP(UDPCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self.connect()

        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp, 'side': side, 'amount': float(amount), 'price': float(price)}
        data = {'type': 'trade', 'data': trade}
        self.transport.sendto(json.dumps(data).encode())


class FundingUDP(UDPCallback):
    async def __call__(self, **kwargs):
        await self.connect()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        data = {'type': 'funding', 'data': kwargs}
        self.transport.sendto(json.dumps(data).encode())


class BookUDP(UDPCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)

    async def __call__(self, *, feed, pair, book, timestamp):
        await self.connect()

        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data, self.depth)
        upd = {'type': 'book', 'feed': feed, 'pair': pair, 'data': data}
        self.transport.sendto(json.dumps(upd).encode())
