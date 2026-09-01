'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pytest
from pymongo import AsyncMongoClient

from cryptofeed.backends.mongo import BookMongo, CandlesMongo, FundingMongo, LiquidationsMongo, OpenInterestMongo, TickerMongo, TradeMongo
from tests.backend.conftest import assert_written, require, run_backend, samples


pytestmark = pytest.mark.backend

DB = 'cryptofeed_test'

CASES = [
    (TradeMongo, 'trades'),
    (TickerMongo, 'ticker'),
    (FundingMongo, 'funding'),
    (OpenInterestMongo, 'open_interest'),
    (LiquidationsMongo, 'liquidations'),
    (CandlesMongo, 'candles'),
    (BookMongo, 'book'),
]


@pytest.fixture
async def mongo():
    host, port = require('mongo')
    client = AsyncMongoClient(host, port, serverSelectionTimeoutMS=5000)
    await client.drop_database(DB)
    yield host, port
    await client.drop_database(DB)
    await client.close()


@pytest.mark.parametrize('backend_class, kind', CASES, ids=[c.__name__ for c, _ in CASES])
async def test_write(mongo, backend_class, kind):
    host, port = mongo
    data = samples(kind)
    backend = backend_class(DB, host=host, port=port, key=backend_class.__name__)

    assert_written(await run_backend(backend, data), len(data))


async def test_data_lands_in_mongo(mongo):
    host, port = mongo
    data = samples('trades')
    backend = TradeMongo(DB, host=host, port=port, key='landed')

    assert_written(await run_backend(backend, data), len(data))

    client = AsyncMongoClient(host, port, serverSelectionTimeoutMS=5000)
    try:
        assert await client[DB]['landed'].count_documents({}) == len(data)
    finally:
        await client.close()
