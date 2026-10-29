from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cryptofeed.defines import OPEN_INTEREST
from cryptofeed.exchanges.bybit import Bybit


pytestmark = pytest.mark.unit


async def test_open_interest_is_single_side():
    # Avoid symbol discovery or any live exchange access.
    feed = object.__new__(Bybit)
    feed.tickers = {}
    feed._std_symbol = lambda symbol, market: 'BTC-USDT-PERP'
    feed.std_symbol_to_exchange_symbol = lambda symbol: 'BTCUSDT'
    feed.callback = AsyncMock()
    conn = SimpleNamespace(subscription={'open_interest': ['BTCUSDT']})
    snapshot = {
        'topic': 'tickers.BTCUSDT',
        'type': 'snapshot',
        'ts': 1792934400123,
        'cs': 31337927919,
        'data': {
            'symbol': 'BTCUSDT',
            'markPrice': '76512.30',
            'indexPrice': '76530.10',
            'openInterest': '62731.528',
            'openInterestValue': '4799760000.12',
            'singleOpenInterest': '31365.764',
            'singleOpenInterestValue': '2399880000.06',
            'fundingRate': '0.00004',
            'nextFundingTime': '1792944000000',
        },
    }
    delta = {
        'topic': 'tickers.BTCUSDT',
        'type': 'delta',
        'ts': 1792934400223,
        'cs': 31337927920,
        'data': {'symbol': 'BTCUSDT', 'openInterest': '62733.528', 'singleOpenInterest': '31366.764'},
    }

    await feed._ticker_open_interest_funding_index(snapshot, 1792934400.2, conn, 'linear')
    await feed._ticker_open_interest_funding_index(delta, 1792934400.3, conn, 'linear')

    calls = [call.args for call in feed.callback.await_args_list]
    assert [channel for channel, _, _ in calls] == [OPEN_INTEREST, OPEN_INTEREST]
    assert [oi.open_interest for _, oi, _ in calls] == [Decimal('31365.764'), Decimal('31366.764')]
