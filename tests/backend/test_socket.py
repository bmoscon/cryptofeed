'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import os
import shutil
import tempfile

import pytest

from cryptofeed import _json as json
from cryptofeed.backends.socket import BookSocket, CandlesSocket, FundingSocket, LiquidationsSocket, OpenInterestSocket, TickerSocket, TradeSocket
from tests.backend.conftest import assert_written, run_backend, samples


pytestmark = pytest.mark.backend

CASES = [
    (TradeSocket, 'trades'),
    (TickerSocket, 'ticker'),
    (FundingSocket, 'funding'),
    (OpenInterestSocket, 'open_interest'),
    (LiquidationsSocket, 'liquidations'),
    (CandlesSocket, 'candles'),
    (BookSocket, 'book'),
]


class Listener:
    def __init__(self):
        self.messages = []
        self._target = 0
        self._enough = asyncio.Event()

    def add(self, message):
        self.messages.append(message)
        if self._target and len(self.messages) >= self._target:
            self._enough.set()

    async def wait(self, count: int, deadline: float = 5.0) -> list:
        self._target = count
        if len(self.messages) < count:
            self._enough.clear()
            async with asyncio.timeout(deadline):
                await self._enough.wait()
        return self.messages


class Datagrams(asyncio.DatagramProtocol):
    def __init__(self, listener: Listener):
        self.listener = listener

    def datagram_received(self, data, addr):
        self.listener.add(data)


async def _serve(start_server) -> tuple:
    listener = Listener()

    async def handle(reader, _writer):
        async for line in reader:
            if line.strip():
                listener.add(json.loads(line))

    return await start_server(handle), listener


@pytest.fixture
async def tcp():
    server, listener = await _serve(lambda handle: asyncio.start_server(handle, '127.0.0.1', 0))
    async with server:
        yield 'tcp://127.0.0.1', server.sockets[0].getsockname()[1], listener


@pytest.fixture
async def uds():
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, 'cf.uds')
    server, listener = await _serve(lambda handle: asyncio.start_unix_server(handle, path))
    try:
        async with server:
            yield f'uds://{path}', None, listener
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
async def udp():
    listener = Listener()
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: Datagrams(listener), local_addr=('127.0.0.1', 0))
    try:
        yield 'udp://127.0.0.1', transport.get_extra_info('sockname')[1], listener
    finally:
        transport.close()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_tcp_write(tcp, backend_class, kind):
    addr, port, listener = tcp
    data = samples(kind)
    backend = backend_class(addr, port=port)

    assert_written(await run_backend(backend, data), len(data))
    messages = await listener.wait(len(data))
    assert len(messages) == len(data)
    assert {message['type'] for message in messages} == {backend.key}


async def test_uds_write(uds):
    addr, port, listener = uds
    data = samples('trades')
    backend = TradeSocket(addr, port=port)

    assert_written(await run_backend(backend, data), len(data))
    assert len(await listener.wait(len(data))) == len(data)


async def test_udp_write(udp):
    addr, port, listener = udp
    data = samples('trades')
    backend = TradeSocket(addr, port=port)

    assert_written(await run_backend(backend, data), len(data))
    assert len(await listener.wait(len(data))) == len(data)


async def test_udp_chunks_oversized_messages(udp):
    addr, port, listener = udp
    data = samples('book', 1)
    backend = BookSocket(addr, port=port, mtu=64)

    assert_written(await run_backend(backend, data), len(data))
    expected = json.loads((await listener.wait(1))[0])['chunks']
    assert expected > 1, 'the message was not chunked'

    datagrams = await listener.wait(expected)
    chunks = [json.loads(datagram) for datagram in datagrams]
    assert len(chunks) == expected
    assert all(len(datagram) <= 64 for datagram in datagrams)
    assert all(chunk['type'] == 'chunked' for chunk in chunks)
    assert json.loads(''.join(chunk['data'] for chunk in chunks))['type'] == backend.key


async def test_unknown_protocol_is_rejected():
    with pytest.raises(ValueError, match='Invalid protocol'):
        TradeSocket('http://127.0.0.1', port=8080)
