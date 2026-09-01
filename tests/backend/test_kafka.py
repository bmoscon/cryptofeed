'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from cryptofeed.backends.kafka import BookKafka, CandlesKafka, FundingKafka, LiquidationsKafka, OpenInterestKafka, TickerKafka, TradeKafka
from tests.backend.conftest import EXCHANGE, SYMBOL, assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

PREFIX = 'cryptofeed-test'

CASES = [
    (TradeKafka, 'trades'),
    (TickerKafka, 'ticker'),
    (FundingKafka, 'funding'),
    (OpenInterestKafka, 'open_interest'),
    (LiquidationsKafka, 'liquidations'),
    (CandlesKafka, 'candles'),
    (BookKafka, 'book'),
]


def key(backend_class) -> str:
    return f'{PREFIX}-{backend_class.__name__}'


@pytest.fixture
async def kafka():
    host, port = require('kafka')
    servers = f'{host}:{port}'

    admin = AIOKafkaAdminClient(bootstrap_servers=servers)
    await admin.start()
    try:
        topics = [NewTopic(f'{key(backend_class)}-{EXCHANGE}-{SYMBOL}', num_partitions=1, replication_factor=1) for backend_class, _ in CASES]
        try:
            await admin.create_topics(topics)
        except TopicAlreadyExistsError:
            pass
    finally:
        await admin.close()
    yield servers


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(kafka, backend_class, kind):
    data = samples(kind)
    backend = backend_class(bootstrap_servers=kafka, key=key(backend_class))

    assert_written(await run_backend(backend, data), len(data))


async def test_illegal_topic_is_rejected(kafka):
    with pytest.raises(ValueError, match='cannot be part of a Kafka topic name'):
        TradeKafka(bootstrap_servers=kafka, key='not a legal topic')
