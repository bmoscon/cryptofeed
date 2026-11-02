from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from cryptofeed.exchanges.gate import Gate


pytestmark = pytest.mark.unit


@pytest.mark.parametrize('window_closed', [False, True])
async def test_candle_volume_is_the_base_currency_amount(window_closed):
    # Avoid symbol discovery or any live exchange access.
    feed = object.__new__(Gate)
    feed.exchange_symbol_to_std_symbol = lambda symbol: 'BTC-USDT'
    feed._candle = AsyncMock()
    message = {
        'time': 1619092863,
        'channel': 'spot.candlesticks',
        'event': 'update',
        'result': {
            't': '1619092860',
            'v': '1154.64627',  # quote currency (USDT)
            'c': '54992.64',
            'h': '54992.64',
            'l': '54976.29',
            'o': '54976.29',
            'n': '1m_BTC_USDT',
            'a': '0.02099',  # base currency (BTC)
            'w': window_closed
        }
    }

    await feed._candles(message, 1619092863.5)

    candle, received_at = feed._candle.await_args.args
    assert candle.symbol == 'BTC-USDT'
    assert candle.interval == '1m'
    assert candle.start == 1619092860
    assert candle.close == Decimal('54992.64')
    assert candle.volume == Decimal('0.02099')
    assert candle.closed is window_closed
    assert received_at == 1619092863.5
