from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from cryptofeed.defines import L2_BOOK, ORDERS, TRADES
from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.generic import CcxtGenericFeed


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


def test_ccxt_generic_feed_requires_credentials():
    context = CcxtConfig(exchange_id="backpack").to_context()

    with pytest.raises(RuntimeError, match="credentials are missing"):
        CcxtGenericFeed(
            exchange_id=context.exchange_id,
            symbols=["BTC-USDT"],
            channels=[ORDERS],
            config_context=context,
        )
