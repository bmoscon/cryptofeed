from __future__ import annotations

import json
import asyncio
from pathlib import Path

import pytest

from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges.backpack import BackpackConfig, BackpackFeed


FIXTURES = Path(__file__).parent.parent / "fixtures" / "backpack"


class FixtureRestClient:
    async def fetch_markets(self):
        return [
            {
                "symbol": "BTC_USDT",
                "type": "spot",
                "status": "TRADING",
            }
        ]

    async def close(self):
        return None


class FixtureWsSession:
    def __init__(self):
        self.open_called = False
        self.subscriptions = []
        self.closed = False

    async def open(self):
        self.open_called = True

    async def subscribe(self, subscriptions):
        self.subscriptions.extend(subscriptions)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_backpack_feed_processes_fixtures(monkeypatch):
    rest = FixtureRestClient()
    ws = FixtureWsSession()

    trades, books = [], []

    async def trade_cb(trade, ts):
        trades.append((trade, ts))

    async def book_cb(book, ts):
        books.append((book, ts))

    feed = BackpackFeed(
        config=BackpackConfig(),
        rest_client_factory=lambda cfg: rest,
        ws_session_factory=lambda cfg: ws,
        symbols=["BTC-USDT"],
        channels=[TRADES, L2_BOOK],
        callbacks={TRADES: [trade_cb], L2_BOOK: [book_cb]},
    )

    await feed.subscribe(None)

    snapshot_payload = json.loads((FIXTURES / "orderbook_snapshot.json").read_text())
    trade_payload = json.loads((FIXTURES / "trade.json").read_text())

    await feed.message_handler(json.dumps(snapshot_payload), None, 0)
    await feed.message_handler(json.dumps(trade_payload), None, 0)

    assert books and trades
    assert books[0][0].symbol == "BTC-USDT"
    assert trades[0][0].price

    metrics = feed.metrics_snapshot()
    assert metrics["ws_errors"] == 0

    health = feed.health(max_snapshot_age=3600)
    assert health.healthy is True or "order book snapshot" not in health.reasons

    await feed.shutdown()
    assert ws.closed is True
