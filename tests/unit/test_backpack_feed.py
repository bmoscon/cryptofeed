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
        self._markets = []

    async def ensure(self):
        self.ensure_calls += 1
        if not self._markets:
            Market = type("Market", (), {})
            market = Market()
            market.normalized_symbol = "BTC-USDT"
            market.native_symbol = "BTC_USDT"
            self._markets = [market]

    def native_symbol(self, symbol: str) -> str:
        return symbol.replace("-", "_")

    def all_markets(self):
        return self._markets


class StubWsSession:
    def __init__(self):
        self.open_called = False
        self.subscriptions = []
        self.closed = False
        self.sent = []

    async def open(self):
        self.open_called = True

    async def subscribe(self, subscriptions):
        self.subscriptions.extend(subscriptions)

    async def read(self):
        await asyncio.sleep(0)
        return "{}"

    async def send(self, payload):
        self.sent.append(payload)

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

    connection = feed.connect()[0][0]
    await connection._open()
    await feed.subscribe(connection)

    assert symbols.ensure_calls == 1
    assert ws.open_called is True
    assert ws.subscriptions
    assert ws.subscriptions[0].channel == "trades"
    assert set(ws.subscriptions[0].symbols) == {"BTC_USDT"}


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

    connection = feed.connect()[0][0]
    await connection._open()
    await feed.subscribe(connection)
    await feed.shutdown()

    assert rest.closed is True
    assert ws.closed is True
