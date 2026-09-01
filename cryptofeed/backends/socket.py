'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from contextlib import suppress
import asyncio
import logging

from cryptofeed import _json as json

from cryptofeed.backends.backend import BackendQueue, BackendBookCallback, BackendCallback


LOG = logging.getLogger(__name__)


class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, backend):
        self.backend = backend
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def error_received(self, exc):
        LOG.error('UDP backend received exception: %s', exc)
        self._drop()

    def connection_lost(self, exc):
        if exc:
            LOG.error('UDP backend connection lost: %s', exc)
        self._drop()

    def _drop(self):
        transport, self.transport = self.transport, None
        if transport is not None:
            transport.close()
        if self.backend.conn is transport:
            self.backend.conn = None
            self.backend.protocol = None


class SocketCallback(BackendQueue):
    hand_off = True
    retryable_exceptions = (OSError,)
    MIN_MTU = 64

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
        super().__init__(**kwargs)
        self.conn_type = addr[:6]
        if self.conn_type not in {'tcp://', 'uds://', 'udp://'}:
            raise ValueError("Invalid protocol specified for SocketCallback")
        if mtu < self.MIN_MTU:
            raise ValueError(f'mtu must be at least {self.MIN_MTU} bytes, not {mtu}')
        self.conn = None
        self.protocol = None
        self.addr = addr[6:]
        self.port = port
        self.mtu = mtu
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.key = key if key else self.default_key

    async def connect(self):
        if self.conn is not None and self.conn.is_closing():
            await self.close()
        if self.conn is None:
            if self.conn_type == 'udp://':
                loop = asyncio.get_running_loop()
                self.conn, self.protocol = await loop.create_datagram_endpoint(
                    lambda: UDPProtocol(self), remote_addr=(self.addr, self.port))
            elif self.conn_type == 'tcp://':
                _, self.conn = await asyncio.open_connection(host=self.addr, port=self.port)
            elif self.conn_type == 'uds://':
                _, self.conn = await asyncio.open_unix_connection(path=self.addr)

    def _datagrams(self, data: str) -> list:
        raw = data.encode()
        if len(raw) <= self.mtu:
            return [raw]

        budget = self.mtu - len(json.dumpb({'type': 'chunked', 'chunks': len(data), 'data': ''}))
        chunks = []
        pos = 0
        while pos < len(data):
            width = budget
            while width > 1:
                encoded = len(json.dumpb(data[pos:pos + width])) - 2   # minus the quotes
                if encoded <= budget:
                    break
                width = max(1, int(width * budget / encoded))
            chunks.append(data[pos:pos + width])
            pos += width

        return [json.dumpb({'type': 'chunked', 'chunks': len(chunks), 'data': chunk}) for chunk in chunks]

    async def write_batch(self, batch: list):
        if self.conn_type == 'udp://':
            conn = self.conn
            if conn is None:
                raise ConnectionError(f'{self.addr}: no UDP transport')
            for update in batch:
                for datagram in self._datagrams(json.dumps({'type': self.key, 'data': update})):
                    conn.sendto(datagram)
            if self.conn is None:
                raise ConnectionError(f'{self.addr}: UDP transport closed mid-batch')
            return

        payload = ''.join(json.dumps({'type': self.key, 'data': update}) + '\n' for update in batch)
        try:
            self.conn.write(payload.encode())
            await self.conn.drain()
        except OSError:
            await self.close()
            raise

    async def close(self):
        conn, self.conn = self.conn, None
        self.protocol = None
        if conn is None:
            return

        with suppress(Exception):
            conn.close()
            if self.conn_type != 'udp://':
                await conn.wait_closed()


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
