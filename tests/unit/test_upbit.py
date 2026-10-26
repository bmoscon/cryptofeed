from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cryptofeed import _json as json
from cryptofeed.defines import L2_BOOK, TICKER
from cryptofeed.exchanges.upbit import Upbit


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_orderbook_only_feeds_channels_subscribed_for_the_symbol():
    feed = object.__new__(Upbit)
    feed._book = AsyncMock()
    feed._ticker = AsyncMock()
    conn = SimpleNamespace(subscription={L2_BOOK: ['KRW-BTC'], TICKER: ['KRW-ETH']})
    msg = {'ty': 'orderbook', 'cd': 'KRW-BTC', 'tms': 1584263923870,
           'obu': [{'ap': 6727000.0, 'as': 0.4744314, 'bp': 6721000.0, 'bs': 0.0014551}]}

    await feed.message_handler(json.dumps(msg), conn, 0.0)

    feed._book.assert_awaited_once()
    feed._ticker.assert_not_awaited()
