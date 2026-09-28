from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from cryptofeed.defines import BUY, POLONIEX, SELL, TRADES
from cryptofeed.exchanges.poloniex import Poloniex


pytestmark = pytest.mark.unit


@pytest.mark.parametrize('batch_size', [1, 2])
@pytest.mark.asyncio
async def test_trade_uses_base_quantity_and_emits_each_batch_entry(batch_size):
    # Avoid symbol discovery or any live exchange access.
    feed = object.__new__(Poloniex)
    feed.exchange_symbol_to_std_symbol = lambda symbol: symbol.replace('_', '-')
    feed.callback = AsyncMock()
    entries = [
        {
            'symbol': 'BTC_USDT',
            'amount': '364.89973',
            'quantity': '0.017',
            'takerSide': 'sell',
            'price': '21464.69',
            'id': '60183607',
            'ts': 1661120814823,
        },
        {
            'symbol': 'ETH_USDT',
            'amount': '3200',
            'quantity': '2',
            'takerSide': 'buy',
            'price': '1600',
            'id': '60183608',
            'ts': 1661120814824,
        },
    ][:batch_size]
    message = {'channel': 'trades', 'data': entries}
    receipt_timestamp = 1661120815.0

    await feed._trade(message, receipt_timestamp)

    assert feed.callback.await_count == batch_size
    for call, entry in zip(feed.callback.await_args_list, entries):
        channel, trade, received_at = call.args
        assert channel == TRADES
        assert trade.exchange == POLONIEX
        assert trade.symbol == entry['symbol'].replace('_', '-')
        assert trade.side == (SELL if entry['takerSide'] == 'sell' else BUY)
        assert trade.amount == Decimal(entry['quantity'])
        assert trade.price == Decimal(entry['price'])
        assert trade.id == entry['id']
        assert trade.timestamp == entry['ts'] / 1000.0
        assert trade.raw == message
        assert received_at == receipt_timestamp
