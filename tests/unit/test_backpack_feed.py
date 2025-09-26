from __future__ import annotations

import asyncio

import pytest

from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges.backpack.config import BackpackConfig
from cryptofeed.exchanges.backpack.feed import BackpackFeed


class StubRestClient:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class StubSymbolService:
    def __init__(self):
        self.ensure_calls = 0

    async def ensure(self):
        self.ensure_calls += 1

    def native_symbol(self, symbol: str) -> str:
        return symbol.replace("-", "_")


class StubWsSession:
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


def test_feature_flag_disabled_raises():
    with pytest.raises(RuntimeError):
        BackpackFeed(feature_flag_enabled=False, symbols=["BTC-USDT"], channels=[TRADES])


@pytest.mark.asyncio
async def test_feed_subscribe_initializes_session():
    rest = StubRestClient()
    symbols = StubSymbolService()
    ws = StubWsSession()

    feed = BackpackFeed(
        config=BackpackConfig(),
        feature_flag_enabled=True,
        rest_client_factory=lambda cfg: rest,
        ws_session_factory=lambda cfg: ws,
        symbol_service=symbols,
        symbols=["BTC-USDT"],
        channels=[TRADES, L2_BOOK],
    )

    await feed.subscribe(None)

    assert symbols.ensure_calls == 1
    assert ws.open_called is True
    assert ws.subscriptions
    assert ws.subscriptions[0].channel == "trades"
    assert set(ws.subscriptions[0].symbols) == {"BTC-USDT"}


@pytest.mark.asyncio
async def test_feed_shutdown_closes_clients():
    rest = StubRestClient()
    ws = StubWsSession()

    feed = BackpackFeed(
        feature_flag_enabled=True,
        rest_client_factory=lambda cfg: rest,
        ws_session_factory=lambda cfg: ws,
        symbol_service=StubSymbolService(),
        symbols=["BTC-USDT"],
        channels=[TRADES],
    )

    await feed.subscribe(None)
    await feed.shutdown()

    assert rest.closed is True
    assert ws.closed is True
