from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cryptofeed import _json as json
from cryptofeed.exchanges.bithumb import Bithumb


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_orderbook_only_feeds_channels_subscribed_for_the_symbol():
    feed = object.__new__(Bithumb)
    feed._book = AsyncMock()
    feed._ticker = AsyncMock()
    conn = SimpleNamespace(subscription={'orderbook': ['KRW-BTC'], 'ticker': ['KRW-ETH']})
    msg = {'type': 'orderbook', 'code': 'KRW-BTC', 'timestamp': 1786371955004253,
           'orderbook_units': [{'ask_price': 91220000, 'bid_price': 91200000, 'ask_size': 0.1176, 'bid_size': 0.0069}]}

    await feed.message_handler(json.dumps(msg), conn, 0.0)

    feed._book.assert_awaited_once()
    feed._ticker.assert_not_awaited()
