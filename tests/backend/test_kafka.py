'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json

import pytest

from cryptofeed.backends.kafka import TradeKafka
from tests.backend.conftest import AMOUNT, EXCHANGE, PRICE, SYMBOL, assert_exact, require, run_backend, sample_trade


TOPIC = f'test-trades-{EXCHANGE}-{SYMBOL}'


@pytest.fixture
async def kafka():
    pytest.importorskip('aiokafka')
    host, port = require('kafka')
    yield f'{host}:{port}'


async def test_trade_round_trip(kafka):
    from aiokafka import AIOKafkaConsumer

    backend = TradeKafka(bootstrap_servers=kafka, key='test-trades', numeric_type=str)
    await run_backend(backend, [sample_trade(str(i)) for i in range(5)], settle=1.0)

    consumer = AIOKafkaConsumer(TOPIC, bootstrap_servers=kafka, auto_offset_reset='earliest',
                                consumer_timeout_ms=5000)
    await consumer.start()
    try:
        messages = []
        async for message in consumer:
            messages.append(json.loads(message.value))
            if len(messages) == 5:
                break
    finally:
        await consumer.stop()

    assert len(messages) == 5, f'expected five messages, got {len(messages)}'
    assert [m['id'] for m in messages] == [str(i) for i in range(5)], 'ordering was not preserved'
    assert messages[0]['exchange'] == EXCHANGE
    assert messages[0]['symbol'] == SYMBOL
    assert_exact(messages[0]['price'], PRICE, 'price')
    assert_exact(messages[0]['amount'], AMOUNT, 'amount')
