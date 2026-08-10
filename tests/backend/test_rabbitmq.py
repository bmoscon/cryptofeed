'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json

import pytest

from cryptofeed.backends.rabbitmq import TradeRabbit
from tests.backend.conftest import AMOUNT, EXCHANGE, PRICE, SYMBOL, assert_exact, require, sample_trade


QUEUE = 'cryptofeed_test'


@pytest.fixture
async def rabbit():
    pytest.importorskip('aio_pika')
    host, _ = require('rabbitmq')
    yield host


async def test_trade_round_trip(rabbit):
    import aio_pika

    backend = TradeRabbit(host=rabbit, queue_name=QUEUE, routing_key=QUEUE, numeric_type=str)
    assert not hasattr(backend, 'start_writer'), 'RabbitMQ now uses the queue - update this test'

    trades = [sample_trade(str(i)) for i in range(5)]
    for trade in trades:
        await backend(trade, trade.timestamp)
    await asyncio.sleep(0.3)

    connection = await aio_pika.connect_robust(f'amqp://{rabbit}')
    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(QUEUE, auto_delete=False, durable=True)
        messages = []
        for _ in range(5):
            message = await queue.get(timeout=5, fail=False)
            if message is None:
                break
            messages.append(json.loads(message.body))
            await message.ack()
        await queue.purge()
    finally:
        await connection.close()

    assert len(messages) == 5, f'expected five messages, got {len(messages)}'
    assert [m['id'] for m in messages] == [str(i) for i in range(5)]
    assert messages[0]['exchange'] == EXCHANGE
    assert messages[0]['symbol'] == SYMBOL
    assert_exact(messages[0]['price'], PRICE, 'price')
    assert_exact(messages[0]['amount'], AMOUNT, 'amount')
