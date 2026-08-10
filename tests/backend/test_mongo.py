'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

import pytest

from cryptofeed.backends.mongo import BookMongo, TradeMongo
from cryptofeed.types import OrderBook
from tests.backend.conftest import AMOUNT, EXCHANGE, PRICE, SYMBOL, TIMESTAMP, assert_exact, require, run_backend, sample_trade


DB = 'cryptofeed_test'
COLLECTION = 'test_trades'
BOOK_COLLECTION = 'test_book'


@pytest.fixture
async def mongo():
    pymongo = pytest.importorskip('pymongo')
    host, port = require('mongo')
    client = pymongo.AsyncMongoClient(host, port)
    await client[DB][COLLECTION].drop()
    await client[DB][BOOK_COLLECTION].drop()
    yield client, host, port
    await client[DB][COLLECTION].drop()
    await client[DB][BOOK_COLLECTION].drop()
    await client.close()


async def test_trade_round_trip(mongo):
    client, host, port = mongo
    backend = TradeMongo(DB, host=host, port=port, key=COLLECTION, numeric_type=str)
    await run_backend(backend, [sample_trade('abc123')])

    documents = await client[DB][COLLECTION].find().to_list(length=10)
    assert len(documents) == 1, f'expected one document, got {len(documents)}'
    document = documents[0]
    assert document['exchange'] == EXCHANGE
    assert document['symbol'] == SYMBOL
    assert document['id'] == 'abc123'
    assert_exact(document['price'], PRICE, 'price')
    assert_exact(document['amount'], AMOUNT, 'amount')
    # timestamps are stored as BSON datetimes, not floats
    assert document['timestamp'].year == 2026


async def test_every_trade_is_written(mongo):
    client, host, port = mongo
    backend = TradeMongo(DB, host=host, port=port, key=COLLECTION, numeric_type=str)
    await run_backend(backend, [sample_trade(str(i)) for i in range(100)], settle=0.8)

    count = await client[DB][COLLECTION].count_documents({})
    assert count == 100, f'expected 100 documents, got {count}'


async def test_book_round_trip(mongo):
    import bson

    client, host, port = mongo
    book = OrderBook(EXCHANGE, SYMBOL, max_depth=2,
                     bids={Decimal('100.5'): Decimal('1.5')},
                     asks={Decimal('101.5'): Decimal('2.5')})
    book.timestamp = TIMESTAMP
    book.raw = None
    book.delta = None
    book.sequence_number = None
    book.checksum = None

    backend = BookMongo(DB, host=host, port=port, key=BOOK_COLLECTION, numeric_type=str)
    await run_backend(backend, [book])

    documents = await client[DB][BOOK_COLLECTION].find().to_list(length=10)
    assert len(documents) == 1, f'expected one document, got {len(documents)}'
    document = documents[0]
    assert document['delta'] is False
    bids = bson.decode(document['bid'])
    asks = bson.decode(document['ask'])
    assert bids == {'100.5': '1.5'}, f'bids came back as {bids}'
    assert asks == {'101.5': '2.5'}, f'asks came back as {asks}'
