from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from cryptofeed.defines import BUY, DERIBIT, LIQUIDATIONS, SELL, TRADES
from cryptofeed.exchanges.deribit import Deribit


pytestmark = pytest.mark.unit


@pytest.mark.parametrize('flag, direction, expected_side', [
    ('T', 'sell', SELL),
    ('T', 'buy', BUY),
    ('M', 'buy', SELL),
    ('M', 'sell', BUY),
])
async def test_liquidation_side_is_the_side_of_the_liquidated_order(flag, direction, expected_side):
    # Avoid symbol discovery or any live exchange access.
    feed = object.__new__(Deribit)
    feed.exchange_symbol_to_std_symbol = lambda symbol: 'BTC-USD-PERP'
    feed.callback = AsyncMock()
    trade = {
        'trade_seq': 306123136,
        'trade_id': '452479061',
        'timestamp': 1792031334853,
        'tick_direction': 2,
        'price': 80158.5,
        'mark_price': 80215.31,
        'index_price': 80207.78,
        'instrument_name': 'BTC-PERPETUAL',
        'direction': direction,
        'amount': 762710.0,
        'liquidation': flag,
    }
    message = {'params': {'data': [trade], 'channel': 'trades.BTC-PERPETUAL.raw'}, 'method': 'subscription', 'jsonrpc': '2.0'}

    await feed._trade(message, 1792031335.0)

    (trade_channel, trade_obj, _), (liq_channel, liquidation, _) = [call.args for call in feed.callback.await_args_list]
    assert trade_channel == TRADES
    assert trade_obj.side == (BUY if direction == 'buy' else SELL)
    assert liq_channel == LIQUIDATIONS
    assert liquidation.exchange == DERIBIT
    assert liquidation.side == expected_side
    assert liquidation.quantity == Decimal('762710.0')
    assert liquidation.id == '452479061'
