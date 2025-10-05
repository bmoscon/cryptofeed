from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.generic import CcxtMetadataCache


LIVE_FLAG = os.getenv("CF_CCXT_TEST_HYPERLIQUID") == "1"
pytestmark = pytest.mark.skipif(
    not LIVE_FLAG,
    reason="set CF_CCXT_TEST_HYPERLIQUID=1 to enable live Hyperliquid checks",
)

ccxt_async = pytest.importorskip("ccxt.async_support")

try:  # optional websocket validation if ccxt.pro is installed
    import ccxt.pro as ccxt_pro  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    ccxt_pro = None


def _proxy_kwargs() -> dict:
    proxy_url = os.getenv("CF_CCXT_HTTP_PROXY")
    if not proxy_url:
        return {}
    return {
        "aiohttp_proxy": proxy_url,
        "proxies": {"http": proxy_url, "https": proxy_url},
    }


def _load_fixture() -> dict:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "ccxt" / "hyperliquid_markets.json"
    return json.loads(fixture_path.read_text())


@pytest.mark.asyncio
async def test_live_market_snapshot_matches_fixture():
    fixture_data = _load_fixture()

    exchange = ccxt_async.hyperliquid(_proxy_kwargs())
    try:
        markets = await exchange.load_markets()
        assert "BTC/USDT:USDT" in markets

        live_market = markets["BTC/USDT:USDT"]
        fixture_market = fixture_data["BTC/USDT:USDT"]

        assert live_market["id"] == fixture_market["id"]
        assert live_market["base"] == fixture_market["base"]
        assert live_market["quote"] == fixture_market["quote"]
        assert live_market["type"].lower() in {"swap", "perpetual"}

        order_book = await exchange.fetch_order_book("BTC/USDT:USDT", limit=10)
        assert order_book["bids"] and order_book["asks"]
        assert order_book["bids"][0][0] > 0
    finally:
        await exchange.close()


@pytest.mark.asyncio
async def test_metadata_cache_handles_live_hyperliquid():
    proxy_kwargs = _proxy_kwargs()
    proxy_url = proxy_kwargs.get("aiohttp_proxy")
    proxies = {"rest": proxy_url, "websocket": proxy_url} if proxy_url else None
    context = CcxtConfig(exchange_id="hyperliquid", proxies=proxies).to_context()

    cache = CcxtMetadataCache("hyperliquid", context=context)
    await cache.ensure()

    assert cache.id_for_symbol("BTC-USDT-PERP") == "BTCUSDT"
    metadata = cache.market_metadata("ETH-USDT-PERP")
    assert metadata["base"] == "ETH"
    assert metadata["quote"] == "USDT"


@pytest.mark.asyncio
@pytest.mark.skipif(ccxt_pro is None, reason="ccxt.pro not installed")
async def test_live_trade_stream_sample():
    proxy_kwargs = _proxy_kwargs()
    exchange = ccxt_pro.hyperliquid(proxy_kwargs)
    try:
        trades = await exchange.watch_trades("BTC/USDT:USDT")
        assert trades
        sample = trades[-1]
        assert sample["symbol"] == "BTC/USDT:USDT"
        assert float(sample["price"]) > 0
    finally:
        await exchange.close()
