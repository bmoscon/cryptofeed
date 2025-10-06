from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from cryptofeed.exchanges.backpack.adapters import BackpackOrderBookAdapter, BackpackTickerAdapter, BackpackTradeAdapter
from cryptofeed.exchanges.backpack.router import BackpackMessageRouter
from cryptofeed.exchanges.backpack.metrics import BackpackMetrics


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
        ticker_adapter=BackpackTickerAdapter(exchange="BACKPACK"),
        trade_callback=collector,
        order_book_callback=None,
        ticker_callback=None,
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
        ticker_adapter=BackpackTickerAdapter(exchange="BACKPACK"),
        trade_callback=None,
        order_book_callback=collector,
        ticker_callback=None,
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


@pytest.mark.asyncio
async def test_router_dispatches_ticker():
    trade_adapter = BackpackTradeAdapter(exchange="BACKPACK")
    orderbook_adapter = BackpackOrderBookAdapter(exchange="BACKPACK")
    ticker_adapter = BackpackTickerAdapter(exchange="BACKPACK")
    collector = CallbackCollector()

    router = BackpackMessageRouter(
        trade_adapter=trade_adapter,
        order_book_adapter=orderbook_adapter,
        ticker_adapter=ticker_adapter,
        trade_callback=None,
        order_book_callback=None,
        ticker_callback=collector,
    )

    await router.dispatch(
        {
            "type": "ticker",
            "symbol": "BTC_USDT",
            "last": "30050",
            "bestBid": "30040",
            "bestAsk": "30060",
            "volume": "10",
            "timestamp": 1_700_000_000_500,
        }
    )

    assert collector.items
    ticker, timestamp = collector.items[0]
    assert ticker.symbol == "BTC-USDT"
    assert float(ticker.bid) == pytest.approx(30040)


@pytest.mark.asyncio
async def test_router_drops_invalid_payload_and_records_metrics():
    metrics = BackpackMetrics()
    router = BackpackMessageRouter(
        trade_adapter=BackpackTradeAdapter(exchange="BACKPACK"),
        order_book_adapter=BackpackOrderBookAdapter(exchange="BACKPACK"),
        ticker_adapter=None,
        trade_callback=None,
        order_book_callback=None,
        ticker_callback=None,
        metrics=metrics,
    )

    await router.dispatch({"type": "trade", "price": "100"})

    snapshot = metrics.snapshot()
    assert snapshot["parser_errors"] == 1
    assert snapshot["dropped_messages"] == 1
