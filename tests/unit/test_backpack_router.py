from __future__ import annotations

import asyncio

import pytest

from cryptofeed.exchanges.backpack.adapters import BackpackOrderBookAdapter, BackpackTradeAdapter
from cryptofeed.exchanges.backpack.router import BackpackMessageRouter


class CallbackCollector:
    def __init__(self):
        self.items = []

    async def __call__(self, item, timestamp):
        self.items.append((item, timestamp))


@pytest.mark.asyncio
async def test_router_dispatches_trade():
    trade_adapter = BackpackTradeAdapter(exchange="BACKPACK")
    orderbook_adapter = BackpackOrderBookAdapter(exchange="BACKPACK")
    collector = CallbackCollector()

    router = BackpackMessageRouter(
        trade_adapter=trade_adapter,
        order_book_adapter=orderbook_adapter,
        trade_callback=collector,
        order_book_callback=None,
    )

    await router.dispatch(
        {
            "type": "trade",
            "symbol": "BTC_USDT",
            "price": "30000",
            "size": "1",
            "side": "buy",
            "ts": 1_700_000_000_000,
        }
    )

    assert collector.items
    trade, timestamp = collector.items[0]
    assert trade.symbol == "BTC-USDT"
    assert timestamp == pytest.approx(1_700_000.0)


@pytest.mark.asyncio
async def test_router_dispatches_order_book_snapshot():
    trade_adapter = BackpackTradeAdapter(exchange="BACKPACK")
    orderbook_adapter = BackpackOrderBookAdapter(exchange="BACKPACK")
    collector = CallbackCollector()

    router = BackpackMessageRouter(
        trade_adapter=trade_adapter,
        order_book_adapter=orderbook_adapter,
        trade_callback=None,
        order_book_callback=collector,
    )

    await router.dispatch(
        {
            "type": "l2_snapshot",
            "symbol": "BTC_USDT",
            "bids": [["30000", "1"]],
            "asks": [["30010", "2"]],
            "timestamp": 1_700_000_000_000,
            "sequence": 42,
        }
    )

    assert collector.items
    book, timestamp = collector.items[0]
    assert book.symbol == "BTC-USDT"
    assert book.sequence_number == 42
    assert timestamp == pytest.approx(1_700_000.0)
