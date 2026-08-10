'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import os
import tempfile
from decimal import Decimal

import pytest
from aiohttp import web

from cryptofeed.backends.socket import TradeSocket
from cryptofeed.backends.zmq import TradeZMQ
from cryptofeed.defines import BUY
from cryptofeed.types import Trade


EXCHANGE = 'TESTEX'
SYMBOL = 'BTC-USD'
PRICE = Decimal('65432.123456789012345678')
AMOUNT = Decimal('0.000000012345678901')
TIMESTAMP = 1786310525.123456


def sample_trade(trade_id='1'):
    return Trade(EXCHANGE, SYMBOL, BUY, AMOUNT, PRICE, TIMESTAMP, id=trade_id, type='market')


async def run_backend(backend, objects, settle=0.25):
    """Start the writer, hand it objects, stop it cleanly."""
    async with asyncio.TaskGroup() as tg:
        backend.start_writer(tg, name='test.backend')
        for obj in objects:
            await backend(obj, obj.timestamp)
        await asyncio.sleep(settle)
        await backend.stop()


def assert_trade_intact(payload: dict, numeric=str):
    assert payload['exchange'] == EXCHANGE
    assert payload['symbol'] == SYMBOL
    assert payload['side'] == BUY
    assert numeric(payload['price']) == numeric(PRICE), 'price lost precision in transit'
    assert numeric(payload['amount']) == numeric(AMOUNT), 'amount lost precision in transit'
    assert float(payload['timestamp']) == pytest.approx(TIMESTAMP)
    assert 'receipt_timestamp' in payload


async def test_socket_tcp_round_trip():
    received = asyncio.Queue()

    async def handle(reader, writer):
        while not reader.at_eof():
            line = await reader.readline()
            if line:
                await received.put(line)

    server = await asyncio.start_server(handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    try:
        backend = TradeSocket('tcp://127.0.0.1', port=port, numeric_type=str)
        await run_backend(backend, [sample_trade()])
        raw = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        server.close()

    payload = json.loads(raw)
    assert payload['type'] == 'trades'
    assert_trade_intact(payload['data'])


async def test_socket_udp_round_trip():
    received = asyncio.Queue()

    class Protocol(asyncio.DatagramProtocol):
        def datagram_received(self, data, addr):
            received.put_nowait(data)

    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(Protocol, local_addr=('127.0.0.1', 0))
    port = transport.get_extra_info('sockname')[1]
    try:
        backend = TradeSocket('udp://127.0.0.1', port=port, numeric_type=str)
        await run_backend(backend, [sample_trade()])
        raw = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        transport.close()

    payload = json.loads(raw)
    assert_trade_intact(payload['data'])


async def test_socket_uds_round_trip():
    received = asyncio.Queue()
    # a unix socket path is capped near 104 bytes, shorter than pytest's tmp_path on macOS
    path = os.path.join(tempfile.mkdtemp(dir='/tmp'), 'cf.sock')

    async def handle(reader, writer):
        while not reader.at_eof():
            line = await reader.readline()
            if line:
                await received.put(line)

    server = await asyncio.start_unix_server(handle, path)
    try:
        backend = TradeSocket(f'uds://{path}', numeric_type=str)
        await run_backend(backend, [sample_trade()])
        raw = await asyncio.wait_for(received.get(), timeout=2)
    finally:
        server.close()

    payload = json.loads(raw)
    assert_trade_intact(payload['data'])


async def test_socket_delivers_every_message():
    received = []

    async def handle(reader, writer):
        while not reader.at_eof():
            line = await reader.readline()
            if line:
                received.append(line)

    server = await asyncio.start_server(handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    try:
        backend = TradeSocket('tcp://127.0.0.1', port=port, numeric_type=str)
        await run_backend(backend, [sample_trade(str(i)) for i in range(50)], settle=0.5)
        await asyncio.sleep(0.2)
    finally:
        server.close()

    ids = [json.loads(line)['data']['id'] for line in received]
    assert ids == [str(i) for i in range(50)], f'expected 50 trades in order, got {len(ids)}'


async def test_zmq_round_trip():
    pytest.importorskip('zmq')
    import zmq
    import zmq.asyncio  # noqa: F811

    ctx = zmq.asyncio.Context.instance()
    subscriber = ctx.socket(zmq.SUB)
    port = subscriber.bind_to_random_port('tcp://127.0.0.1')
    subscriber.setsockopt(zmq.SUBSCRIBE, b'')
    try:
        backend = TradeZMQ(port=port, numeric_type=str)
        # a PUB socket drops messages sent before the subscriber has connected, so let the
        # subscription settle before writing
        async with asyncio.TaskGroup() as tg:
            backend.start_writer(tg, name='test.zmq')
            await asyncio.sleep(0.3)
            trade = sample_trade()
            await backend(trade, trade.timestamp)
            raw = await asyncio.wait_for(subscriber.recv_string(), timeout=3)
            await backend.stop()
    finally:
        subscriber.close()

    topic, _, body = raw.partition(' ')
    assert topic == f'{EXCHANGE}-trades-{SYMBOL}', f'unexpected topic {topic!r}'
    assert_trade_intact(json.loads(body))


async def test_http_backend_posts_to_a_local_server():
    from cryptofeed.backends.http import HTTPCallback

    received = asyncio.Queue()

    async def handler(request):
        await received.put(await request.text())
        return web.Response(text='ok')

    app = web.Application()
    app.router.add_post('/write', handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = runner.addresses[0][1]

    try:
        backend = HTTPCallback(f'http://127.0.0.1:{port}/write')
        await backend.http_write('line one\nline two')
        body = await asyncio.wait_for(received.get(), timeout=3)
        await backend.session.close()
    finally:
        await runner.cleanup()

    assert 'line one' in body and 'line two' in body
