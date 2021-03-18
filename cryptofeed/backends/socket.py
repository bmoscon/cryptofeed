'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from textwrap import wrap

from yapic import json

from cryptofeed.backends.backend import (BackendCandlesCallback, BackendQueue, BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)


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


class SocketCallback(BackendQueue):
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

    async def writer(self):
        while True:
            await self.connect()
            async with self.read_queue() as update:
                if self.conn_type == 'udp://':
                    if len(update) > self.mtu:
                        chunks = wrap(update, self.mtu)
                        for chunk in chunks:
                            msg = json.dumps({'type': 'chunked', 'chunks': len(chunks), 'data': chunk}).encode()
                            self.conn.sendto(msg)
                    else:
                        self.conn.sendto(update.encode())
                else:
                    self.conn.write(update.encode())

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

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        data = {'type': self.key, 'data': data}
        data = json.dumps(data)
        await self.queue.put(data)


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


class LiquidationsSocket(SocketCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoSocket(SocketCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsSocket(SocketCallback, BackendTransactionsCallback):
    default_key = 'transactions'


class CandlesSocket(SocketCallback, BackendCandlesCallback):
    default_key = 'candles'
