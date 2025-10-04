from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from cryptofeed.exchanges.backpack.symbols import BackpackSymbolService, BackpackMarket


class DummyRestClient:
    def __init__(self, markets):
        self._markets = markets
        self.calls = 0

    async def fetch_markets(self):
        self.calls += 1
        await asyncio.sleep(0)
        return self._markets


MOCK_MARKETS = [
    {
        "symbol": "BTC_USDT",
        "base": "BTC",
        "quote": "USDT",
        "type": "spot",
        "status": "TRADING",
        "precision": {"price": 2, "amount": 5},
        "limits": {"amount": {"min": "0.0001"}},
        "sequence": True,
    },
    {
        "symbol": "BTC_USD_PERP",
        "base": "BTC",
        "quote": "USD",
        "type": "perpetual",
        "status": "TRADING",
        "precision": {"price": 1, "amount": 3},
        "limits": {"amount": {"min": "0.001"}},
        "sequence": True,
    },
]


@pytest.mark.asyncio
async def test_symbol_service_caches_results():
    rest = DummyRestClient(MOCK_MARKETS)
    service = BackpackSymbolService(rest_client=rest, ttl_seconds=900)

    await service.ensure()
    await service.ensure()

    assert rest.calls == 1
    market = service.get_market("BTC-USDT")
    assert isinstance(market, BackpackMarket)
    assert market.instrument_type == "SPOT"
    assert market.native_symbol == "BTC_USDT"


@pytest.mark.asyncio
async def test_symbol_service_force_refresh():
    rest = DummyRestClient(MOCK_MARKETS)
    service = BackpackSymbolService(rest_client=rest, ttl_seconds=900)

    await service.ensure()
    await service.ensure(force=True)

    assert rest.calls == 2


@pytest.mark.asyncio
async def test_symbol_lookup_missing_symbol():
    rest = DummyRestClient(MOCK_MARKETS)
    service = BackpackSymbolService(rest_client=rest)

    await service.ensure()

    with pytest.raises(KeyError):
        service.get_market("ETH-USDT")


@pytest.mark.asyncio
async def test_native_to_normalized_mapping():
    rest = DummyRestClient(MOCK_MARKETS)
    service = BackpackSymbolService(rest_client=rest)

    await service.ensure()

    assert service.native_symbol("BTC-USDT") == "BTC_USDT"
    assert service.normalized_symbol("BTC_USDT") == "BTC-USDT"
    assert service.normalized_symbol("BTC_USD_PERP") == "BTC-USD-PERP"
