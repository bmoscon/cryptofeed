from __future__ import annotations

import asyncio

import pytest

from cryptofeed.exchanges.backpack.config import BackpackConfig
from cryptofeed.exchanges.backpack.rest import BackpackRestClient, BackpackRestError


class StubHTTPAsyncConn:
    def __init__(self):
        self.requests = []
        self.closed = False
        self.proxy = None
        self._responses = {}

    def queue_response(self, url, response, params=None):
        self._responses[(url, tuple(sorted((params or {}).items())))] = response

    async def read(self, url, params=None, **kwargs):
        key = (url, tuple(sorted((params or {}).items())))
        self.requests.append((url, params))
        if key not in self._responses:
            raise AssertionError(f"Unexpected request {key}")
        return self._responses[key]

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_fetch_markets_returns_list(monkeypatch):
    conn = StubHTTPAsyncConn()
    config = BackpackConfig()
    url = f"{config.rest_endpoint}/api/v1/markets"
    conn.queue_response(url, "[{\"symbol\": \"BTC_USDT\"}]")

    client = BackpackRestClient(config, http_conn_factory=lambda: conn)

    markets = await client.fetch_markets()

    assert markets == [{"symbol": "BTC_USDT"}]
    assert conn.requests == [(url, None)]


@pytest.mark.asyncio
async def test_fetch_order_book_parses_snapshot():
    conn = StubHTTPAsyncConn()
    config = BackpackConfig()
    url = f"{config.rest_endpoint}/api/v1/depth"
    conn.queue_response(
        url,
        '{"bids": [["30000","1"]], "asks": [["30010","2"]], "sequence": 42, "timestamp": 1700}',
        params={"symbol": "BTC_USDT", "limit": 50},
    )

    client = BackpackRestClient(config, http_conn_factory=lambda: conn)
    snapshot = await client.fetch_order_book(native_symbol="BTC_USDT", depth=50)

    assert snapshot.symbol == "BTC_USDT"
    assert snapshot.sequence == 42
    assert snapshot.timestamp_ms == 1700
    assert snapshot.bids[0] == ["30000", "1"]


@pytest.mark.asyncio
async def test_fetch_order_book_invalid_payload():
    conn = StubHTTPAsyncConn()
    config = BackpackConfig()
    url = f"{config.rest_endpoint}/api/v1/depth"
    conn.queue_response(url, '{}', params={"symbol": "BTC_USDT", "limit": 10})

    client = BackpackRestClient(config, http_conn_factory=lambda: conn)
    with pytest.raises(BackpackRestError):
        await client.fetch_order_book(native_symbol="BTC_USDT", depth=10)


@pytest.mark.asyncio
async def test_client_close():
    conn = StubHTTPAsyncConn()
    config = BackpackConfig()
    client = BackpackRestClient(config, http_conn_factory=lambda: conn)

    await client.close()
    assert conn.closed is True
