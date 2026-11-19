from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cryptofeed import _json as json
from cryptofeed.defines import BID
from cryptofeed.exchanges import Coinbase
from cryptofeed.exceptions import MissingSequenceNumber

pytestmark = pytest.mark.unit


def book_message(sequence, size, event_type='update'):
    msg = {
        'channel': 'l2_data',
        'timestamp': '2026-11-01T00:00:00Z',
        'events': [{'type': event_type, 'product_id': 'BTC-USD', 'updates': [
            {'side': 'bid', 'price_level': '100', 'new_quantity': str(size)},
        ]}],
    }
    if sequence is not None:
        msg['sequence_num'] = sequence
    return json.dumps(msg)


@pytest.mark.asyncio
@pytest.mark.parametrize('stale_sequence', [5, 6])
async def test_stale_level2_messages_cannot_overwrite_newer_book(stale_sequence):
    feed = Coinbase()
    feed.exchange_symbol_to_std_symbol = lambda symbol: symbol
    feed.book_callback = AsyncMock()
    conn = SimpleNamespace(uuid='connection')
    await feed.message_handler(book_message(5, 1, 'snapshot'), conn, 1)
    await feed.message_handler(book_message(6, 2), conn, 2)
    await feed.message_handler(book_message(stale_sequence, 9), conn, 3)
    assert feed._l2_book['BTC-USD'].book[BID][Decimal(100)] == Decimal(2)
    assert feed.book_callback.await_count == 2
    await feed.message_handler(book_message(7, 3), conn, 4)
    assert feed._l2_book['BTC-USD'].book[BID][Decimal(100)] == Decimal(3)
    assert feed.book_callback.await_count == 3


@pytest.mark.asyncio
async def test_forward_gap_still_requires_recovery():
    feed = Coinbase()
    feed.exchange_symbol_to_std_symbol = lambda symbol: symbol
    feed.book_callback = AsyncMock()
    conn = SimpleNamespace(uuid='connection')
    await feed.message_handler(book_message(5, 1, 'snapshot'), conn, 1)
    with pytest.raises(MissingSequenceNumber):
        await feed.message_handler(book_message(7, 9), conn, 2)
    assert feed._l2_book['BTC-USD'].book[BID][Decimal(100)] == Decimal(1)
    assert feed.book_callback.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('conn', [SimpleNamespace(uuid='connection'), SimpleNamespace()])
async def test_messages_without_sequence_metadata_remain_accepted(conn):
    feed = Coinbase()
    feed.exchange_symbol_to_std_symbol = lambda symbol: symbol
    feed.book_callback = AsyncMock()
    await feed.message_handler(book_message(None, 1, 'snapshot'), conn, 1)
    await feed.message_handler(book_message(None, 2), conn, 2)
    assert feed._l2_book['BTC-USD'].book[BID][Decimal(100)] == Decimal(2)
    assert feed.book_callback.await_count == 2
