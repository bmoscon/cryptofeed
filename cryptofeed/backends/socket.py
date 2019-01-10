'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import asyncio
import json

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert
from cryptofeed.defines import TRADES, FUNDING


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


class SocketCallback:
    def __init__(self, addr: str, port=None, **kwargs):
        """
        Common parent class for all socket callbacks

        Parameters
        ----------
        addr: str
          Address for connection. Should be in the format:
          <protocol>://<address>
          Example:
          tcp://127.0.0.1
          uds:///tmp/crypto.uds
          udp://127.0.0.1
        port: int
          port for connection. Should not be specified for UDS connections
        """
        self.conn_type = addr[:6]
        if self.conn_type not in {'tcp://', 'uds://', 'udp://'}:
            raise ValueError("Invalid protocol specified for SocketCallback")
        self.conn = None
        self.protocol = None
        self.addr = addr[6:]
        self.port = port

    async def connect(self):
        if not self.conn:
            if self.conn_type == 'udp://':
                loop = asyncio.get_event_loop()
                self.conn, self.protocol = await loop.create_datagram_endpoint(
                    lambda: UDPProtocol(loop), remote_addr=(self.addr, self.port))
            elif self.conn_type == 'tcp://':
                _, self.conn = await asyncio.open_connection(host=self.addr, port=self.port)
            elif self.conn_type == 'uds://':
                _, self.conn = await asyncio.open_unix_connection(path=self.addr)

    def write(self, data):
        data = json.dumps(data).encode()
        if self.conn_type == 'udp://':
            self.conn.sendto(data)
        else:
            self.conn.write(data)


class TradeSocket(SocketCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self.connect()

        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp, 'side': side, 'amount': float(amount), 'price': float(price)}
        data = {'type': TRADES, 'data': trade}
        self.write(data)


class FundingSocket(SocketCallback):
    async def __call__(self, **kwargs):
        await self.connect()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        data = {'type': FUNDING, 'data': kwargs}
        self.write(data)


class BookSocket(SocketCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.depth = kwargs.get('depth', None)
        self.previous = {BID: {}, ASK: {}}

    async def __call__(self, *, feed, pair, book, timestamp):
        await self.connect()

        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data, self.depth)
        upd = {'type': 'book', 'feed': feed, 'pair': pair, 'data': data}

        if self.depth:
            if upd['data'][BID] == self.previous[BID] and upd['data'][ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = upd['data'][ASK]
            self.previous[BID] = upd['data'][BID]

        self.write(upd)
