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


@pytest.mark.asyncio
async def test_nbbo_withdraws_empty_venue_quotes():
    callback = AsyncMock()
    nbbo = NBBO(callback, ['BTC-USD'])
    await nbbo(OrderBook('first', 'BTC-USD', bids={Decimal(100): Decimal(1)}, asks={Decimal(101): Decimal(1)}), 0)
    await nbbo(OrderBook('second', 'BTC-USD', bids={Decimal(99): Decimal(2)}, asks={Decimal(102): Decimal(2)}), 1)
    await nbbo(OrderBook('first', 'BTC-USD', bids={}, asks={}), 2)
    assert callback.await_args.args == ('BTC-USD', Decimal(99), Decimal(2), Decimal(102), Decimal(2), 'second', 'second')


@pytest.mark.asyncio
async def test_nbbo_withdraws_only_the_empty_side():
    callback = AsyncMock()
    nbbo = NBBO(callback, ['BTC-USD'])
    await nbbo(OrderBook('first', 'BTC-USD', bids={Decimal(100): Decimal(1)}, asks={Decimal(101): Decimal(1)}), 0)
    await nbbo(OrderBook('second', 'BTC-USD', bids={Decimal(99): Decimal(2)}, asks={Decimal(102): Decimal(2)}), 1)
    await nbbo(OrderBook('first', 'BTC-USD', bids={}, asks={Decimal(101): Decimal(1)}), 2)
    assert callback.await_args.args == ('BTC-USD', Decimal(99), Decimal(2), Decimal(101), Decimal(1), 'second', 'first')


@pytest.mark.asyncio
async def test_nbbo_emits_restored_quote_after_empty_book():
    callback = AsyncMock()
    nbbo = NBBO(callback, ['BTC-USD'])
    await nbbo(book('BTC-USD'), 0)
    await nbbo(OrderBook('exchange', 'BTC-USD', bids={}, asks={}), 1)
    await nbbo(book('BTC-USD'), 2)
    assert callback.await_count == 2
    assert callback.await_args.args[:2] == ('BTC-USD', Decimal(100))
