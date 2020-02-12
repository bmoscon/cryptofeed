'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import asyncio
import json
from textwrap import wrap

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback, BackendOpenInterestCallback


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
    def __init__(self, addr: str, port=None, numeric_type=float, key=None, mtu=1400, **kwargs):
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
        mtu: int
          MTU for UDP message size. Should be slightly less than actual MTU for overhead
        """
        self.conn_type = addr[:6]
        if self.conn_type not in {'tcp://', 'uds://', 'udp://'}:
            raise ValueError("Invalid protocol specified for SocketCallback")
        self.conn = None
        self.protocol = None
        self.addr = addr[6:]
        self.port = port
        self.mtu = mtu
        self.numeric_type = numeric_type
        self.key = key if key else self.default_key

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

    async def write(self, feed, pair, timestamp, data):
        await self.connect()
        data = {'type': self.key, 'data': data}
        data = json.dumps(data)

        if self.conn_type == 'udp://':
            if len(data) > self.mtu:
                chunks = wrap(data, self.mtu)
                for chunk in chunks:
                    msg = json.dumps({'type': 'chunked', 'chunks': len(chunks), 'data': chunk}).encode()
                    self.conn.sendto(msg)
            else:
                self.conn.sendto(data.encode())
        else:
            self.conn.write(data.encode())


class TradeSocket(SocketCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingSocket(SocketCallback, BackendFundingCallback):
    default_key = 'funding'


class BookSocket(SocketCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaSocket(SocketCallback, BackendBookDeltaCallback):
    default_key = 'book'


class TickerSocket(SocketCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestSocket(SocketCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'
