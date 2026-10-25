from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from cryptofeed.defines import BUY, BYBIT, LIQUIDATIONS, SELL
from cryptofeed.exchanges.bybit import Bybit


pytestmark = pytest.mark.unit


@pytest.mark.parametrize('position_side, expected_side', [('Buy', SELL), ('Sell', BUY)])
async def test_liquidation_side_is_the_side_of_the_liquidation_order(position_side, expected_side):
    # Avoid symbol discovery or any live exchange access.
    feed = object.__new__(Bybit)
    feed.exchange_symbol_to_std_symbol = lambda symbol: 'BTC-USDT-PERP'
    feed.callback = AsyncMock()
    entry = {'T': 1792933987115, 's': 'BTCUSDT', 'S': position_side, 'v': '0.012', 'p': '76500.5'}
    message = {'topic': 'allLiquidation.BTCUSDT', 'type': 'snapshot', 'ts': 1792933987204, 'data': [entry]}

    await feed._liquidation(message, 1792933987.5)

    channel, liquidation, received_at = feed.callback.await_args.args
    assert channel == LIQUIDATIONS
    assert liquidation.exchange == BYBIT
    assert liquidation.symbol == 'BTC-USDT-PERP'
    assert liquidation.side == expected_side
    assert liquidation.quantity == Decimal('0.012')
    assert liquidation.price == Decimal('76500.5')
    assert received_at == 1792933987.5
