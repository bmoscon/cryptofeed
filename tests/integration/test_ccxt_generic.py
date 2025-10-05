from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from cryptofeed.defines import L2_BOOK, ORDERS, TRADES
from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.generic import CcxtGenericFeed
from tests.integration.conftest import _FakeProClient


@pytest.mark.asyncio
async def test_ccxt_generic_feed_rest_ws_flow(ccxt_fake_clients):
    registry = ccxt_fake_clients

    context = CcxtConfig(
        exchange_id="backpack",
        api_key="unit-key",
        secret="unit-secret",
        proxies={
            "rest": "http://rest-proxy:8000",
            "websocket": "socks5://ws-proxy:9000",
        },
        transport={
            "snapshot_interval": 15,
            "websocket_enabled": True,
        },
    ).to_context()

    feed = CcxtGenericFeed(
        exchange_id=context.exchange_id,
        symbols=["BTC-USDT"],
        channels=[TRADES, L2_BOOK, ORDERS],
        config_context=context,
    )

    books = []
    trades = []
    auth_calls = []

    feed.register_callback(L2_BOOK, lambda snapshot: books.append(snapshot))
    feed.register_callback(TRADES, lambda trade: trades.append(trade))

    async def auth_callback(client):
        auth_calls.append(client.kwargs.get("apiKey"))

    feed.register_authentication_callback(auth_callback)

    await feed.bootstrap_l2()
    await feed.stream_trades_once()

    assert len(books) == 1
    book = books[0]
    assert book.symbol == "BTC-USDT"
    assert book.sequence == 1234
    assert book.bids[0][0] == Decimal("100.1")
    assert book.asks[0][0] == Decimal("100.3")

    assert len(trades) == 1
    trade = trades[0]
    assert trade.price == Decimal("101.25")
    assert trade.amount == Decimal("0.75")
    assert trade.trade_id == "trade-1"

    # Auth callbacks invoked for both REST and WS transports
    assert auth_calls.count("unit-key") >= 2

    # Proxy settings applied to fake clients
    rest_client = registry["rest"][0]
    ws_client = registry["ws"][0]
    assert rest_client.kwargs.get("aiohttp_proxy") == "http://rest-proxy:8000"
    assert ws_client.kwargs.get("aiohttp_proxy") == "socks5://ws-proxy:9000"

    await feed.close()


@pytest.mark.asyncio
async def test_ccxt_generic_feed_hyperliquid_flow(ccxt_fake_clients):
    registry = ccxt_fake_clients

    context = CcxtConfig(exchange_id="hyperliquid").to_context()

    feed = CcxtGenericFeed(
        exchange_id="hyperliquid",
        symbols=["BTC-USDT-PERP"],
        channels=[TRADES, L2_BOOK],
        config_context=context,
    )

    books: list = []
    trades: list = []

    feed.register_callback(L2_BOOK, lambda snapshot: books.append(snapshot))
    feed.register_callback(TRADES, lambda trade: trades.append(trade))

    await feed.bootstrap_l2()
    await feed.stream_trades_once()

    assert books and trades

    book = books[0]
    assert book.symbol == "BTC-USDT-PERP"
    assert book.sequence == 901
    assert book.bids[0][0] == Decimal("25000.4")

    trade = trades[0]
    assert trade.symbol == "BTC-USDT-PERP"
    assert trade.price == Decimal("25001.1")
    assert trade.sequence == 1337

    # Cache should expose ccxt identifiers for Hyperliquid perpetuals
    assert feed.cache.id_for_symbol("BTC-USDT-PERP") == "BTCUSDT"
    assert feed.cache.request_symbol("BTC-USDT-PERP") == "BTC/USDT:USDT"

    rest_clients = [client for client in registry["rest"] if client.exchange_id == "hyperliquid"]
    assert rest_clients, "expected hyperliquid rest client to be constructed"

    await feed.close()


def test_ccxt_generic_feed_requires_credentials():
    context = CcxtConfig(exchange_id="backpack").to_context()

    with pytest.raises(RuntimeError, match="credentials are missing"):
        CcxtGenericFeed(
            exchange_id=context.exchange_id,
            symbols=["BTC-USDT"],
            channels=[ORDERS],
            config_context=context,
        )


@pytest.mark.asyncio
async def test_ccxt_generic_feed_ws_fallback_to_rest(ccxt_fake_clients, monkeypatch):
    context = CcxtConfig(
        exchange_id="backpack",
        api_key="unit-key",
        secret="unit-secret",
        transport={"websocket_enabled": True},
    ).to_context()

    # Force websocket client to raise to trigger fallback
    async def failing_watch_trades(self, symbol):
        raise NotImplementedError("ws not supported")

    monkeypatch.setattr(_FakeProClient, "watch_trades", failing_watch_trades)

    feed = CcxtGenericFeed(
        exchange_id=context.exchange_id,
        symbols=["BTC-USDT"],
        channels=[TRADES],
        config_context=context,
    )

    trades = []
    feed.register_callback(TRADES, lambda trade: trades.append(trade))

    await feed.stream_trades_once()

    assert feed.rest_only is True
    assert feed.websocket_enabled is False
    assert trades == []

    await feed.close()
