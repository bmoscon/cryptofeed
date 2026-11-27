from unittest.mock import AsyncMock

import pytest

from cryptofeed.exchanges.bitget import Bitget
from cryptofeed.util.history import CandleWatermark


pytestmark = pytest.mark.unit


async def test_monthly_candle_stops_at_the_start_of_the_next_month():
    feed = object.__new__(Bitget)
    feed.candle_interval = '1M'
    feed.candle_closed_only = True
    feed.candle_watermark = CandleWatermark()
    feed._candle_rows = {}
    feed.callback = AsyncMock()
    # the August 2026 bar opens 2026-08-01 00:00 UTC+8, the September bar 31 days later
    msg = {'action': 'update', 'ts': 1788192000500, 'data': [
        ['1785513600000', '1', '1', '1', '1', '0', '0', '0'],
        ['1788192000000', '1', '1', '1', '1', '0', '0', '0'],
    ]}

    await feed._candle(msg, 0, 'BTC-USDT')

    candle = feed.callback.await_args.args[1]
    assert candle.stop == 1788192000
