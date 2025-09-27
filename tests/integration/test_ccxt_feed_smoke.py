from __future__ import annotations

from decimal import Decimal

import pytest

from cryptofeed.defines import ASK, BID, L2_BOOK, TRADES
from cryptofeed.feedhandler import FeedHandler
from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.feed import CcxtFeed


@pytest.mark.asyncio
async def test_feedhandler_smoke_cycle(ccxt_fake_clients):
    registry = ccxt_fake_clients

    ccxt_config = CcxtConfig(
        exchange_id="backpack",
        api_key="smoke-key",
        secret="smoke-secret",
        proxies={
            "rest": "http://rest-proxy:7000",
            "websocket": "socks5://ws-proxy:7001",
        },
    )

    trades = []
    books = []

    async def trade_handler(trade, timestamp):  # pragma: no cover - invoked in test
        trades.append((trade, timestamp))

    async def book_handler(book, timestamp):  # pragma: no cover - invoked in test
        books.append((book, timestamp))

    fh = FeedHandler()
    feed = CcxtFeed(
        config=ccxt_config.to_exchange_config(),
        symbols=["BTC-USDT"],
        channels=[TRADES, L2_BOOK],
        callbacks={},
    )
    fh.add_feed(feed)

    await feed._initialize_ccxt_feed()
    feed.callbacks[TRADES] = []
    feed.callbacks[L2_BOOK] = []
    feed._ccxt_feed.channels.add(TRADES)
    feed._ccxt_feed.channels.add(L2_BOOK)
    feed._ccxt_feed.register_callback(TRADES, lambda payload: trades.append((payload, payload.timestamp)))
    feed._ccxt_feed.register_callback(L2_BOOK, lambda payload: books.append((payload, payload.timestamp)))
    await feed._ccxt_feed.bootstrap_l2()
    await feed._ccxt_feed.stream_trades_once()
    await feed._ccxt_feed.close()

    assert len(trades) == 1
    trade, ts = trades[0]
    assert trade.price == Decimal("101.25")
    assert ts == pytest.approx(trade.timestamp)

    assert len(books) == 1
    book_snapshot, _ = books[0]
    assert book_snapshot.bids[0][0] == Decimal("100.1")
    assert book_snapshot.asks[0][0] == Decimal("100.3")

    # Verify feed instantiated via FeedHandler and proxy/auth propagated
    rest_client = registry["rest"][0]
    ws_client = registry["ws"][0]
    assert rest_client.kwargs.get("aiohttp_proxy") == "http://rest-proxy:7000"
    assert ws_client.kwargs.get("aiohttp_proxy") == "socks5://ws-proxy:7001"
