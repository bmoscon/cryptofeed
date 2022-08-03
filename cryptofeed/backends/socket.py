'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio
import logging
from textwrap import wrap

from yapic import json

from cryptofeed.backends.backend import BackendQueue, BackendBookCallback, BackendCallback


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
    def __init__(self, addr: str, port=None, none_to=None, numeric_type=float, key=None, mtu=1400, **kwargs):
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
        self.none_to = none_to
        self.key = key if key else self.default_key
        self.running = True

    async def writer(self):
        while self.running:
            await self.connect()
            async with self.read_queue() as updates:
                for update in updates:
                    data = {'type': self.key, 'data': update}
                    data = json.dumps(data)
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


class TradeSocket(SocketCallback, BackendCallback):
    default_key = 'trades'


class FundingSocket(SocketCallback, BackendCallback):
    default_key = 'funding'


class BookSocket(SocketCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class TickerSocket(SocketCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestSocket(SocketCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsSocket(SocketCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesSocket(SocketCallback, BackendCallback):
    default_key = 'candles'


class OrderInfoSocket(SocketCallback, BackendCallback):
    default_key = 'order_info'


class TransactionsSocket(SocketCallback, BackendCallback):
    default_key = 'transactions'


class BalancesSocket(SocketCallback, BackendCallback):
    default_key = 'balances'


class FillsSocket(SocketCallback, BackendCallback):
    default_key = 'fills'
