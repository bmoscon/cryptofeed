from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from cryptofeed.nbbo import NBBO
from cryptofeed.types import OrderBook


pytestmark = pytest.mark.unit


def book(symbol, bid=100):
    return OrderBook('exchange', symbol, bids={Decimal(bid): Decimal(1)}, asks={Decimal(bid + 1): Decimal(2)})


@pytest.mark.asyncio
async def test_nbbo_identical_quotes_for_different_symbols():
    callback = AsyncMock()
    nbbo = NBBO(callback, ['BTC-USD', 'ETH-USD'])
    await nbbo(book('BTC-USD'), 0)
    await nbbo(book('ETH-USD'), 1)
    assert [call.args[0] for call in callback.await_args_list] == ['BTC-USD', 'ETH-USD']


@pytest.mark.asyncio
async def test_nbbo_deduplicates_each_symbol_when_updates_interleave():
    callback = AsyncMock()
    nbbo = NBBO(callback, ['BTC-USD', 'ETH-USD'])
    await nbbo(book('BTC-USD'), 0)
    await nbbo(book('ETH-USD', 50), 1)
    await nbbo(book('BTC-USD'), 2)
    await nbbo(book('ETH-USD', 50), 3)
    assert callback.await_count == 2
    await nbbo(book('BTC-USD', 101), 4)
    assert callback.await_count == 3
    assert callback.await_args.args[:2] == ('BTC-USD', Decimal(101))
