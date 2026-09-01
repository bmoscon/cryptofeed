'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest
import zmq
import zmq.asyncio

from cryptofeed.backends.zmq import BookZMQ, CandlesZMQ, FundingZMQ, LiquidationsZMQ, OpenInterestZMQ, TickerZMQ, TradeZMQ
from tests.backend.conftest import assert_written, run_backend, samples


pytestmark = pytest.mark.backend

CASES = [
    (TradeZMQ, 'trades'),
    (TickerZMQ, 'ticker'),
    (FundingZMQ, 'funding'),
    (OpenInterestZMQ, 'open_interest'),
    (LiquidationsZMQ, 'liquidations'),
    (CandlesZMQ, 'candles'),
    (BookZMQ, 'book'),
]


@pytest.fixture
async def subscriber():
    socket = zmq.asyncio.Context.instance().socket(zmq.SUB)
    socket.setsockopt(zmq.SUBSCRIBE, b'')
    port = socket.bind_to_random_port('tcp://127.0.0.1')
    try:
        yield port
    finally:
        socket.close()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(subscriber, backend_class, kind):
    data = samples(kind)
    backend = backend_class(host='127.0.0.1', port=subscriber)

    assert_written(await run_backend(backend, data), len(data))


async def test_static_key(subscriber):
    data = samples('trades')
    backend = TradeZMQ(host='127.0.0.1', port=subscriber, dynamic_key=False)

    assert_written(await run_backend(backend, data), len(data))
