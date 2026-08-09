'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import pytest

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import TRADES
from cryptofeed.exceptions import UnsupportedSymbol
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol, Symbols


INSTRUMENTS = '{"instruments": [{"base": "BTC", "quote": "USD"}, {"base": "ETH", "quote": "USD"}]}'


class FakeHTTP:
    def __init__(self, response=INSTRUMENTS):
        self.response = response
        self.requests = []

    async def read(self, address, header=None, **kwargs):
        self.requests.append(address)
        return self.response

    async def close(self):
        pass


class FakeExchange(Feed):
    id = 'FAKEX'
    websocket_endpoints = [WebsocketEndpoint('wss://fake.invalid')]
    rest_endpoints = [RestEndpoint('https://fake.invalid', routes=Routes('/instruments'))]
    websocket_channels = {TRADES: 'trades'}

    @classmethod
    def _parse_symbol_data(cls, data):
        ret = {}
        info = {'instrument_type': {}}
        for entry in data['instruments']:
            s = Symbol(entry['base'], entry['quote'])
            ret[s.normalized] = f"{entry['base']}{entry['quote']}"
            info['instrument_type'][s.normalized] = s.type
        return ret, info


@pytest.fixture(autouse=True)
def clean_registry():
    Symbols.clear()
    yield
    Symbols.clear()


async def test_load_symbols_populates_registry():
    conn = FakeHTTP()
    syms = await FakeExchange.load_symbols(conn=conn)
    assert syms == {'BTC-USD': 'BTCUSD', 'ETH-USD': 'ETHUSD'}
    assert conn.requests == ['https://fake.invalid/instruments']
    assert Symbols.populated('FAKEX')


async def test_constructor_is_network_free_and_defers_bad_symbols():
    feed = FakeExchange(symbols=['DOGE-USD'], channels=[TRADES], config={'log': {'disabled': True}})
    feed.http_conn = FakeHTTP()
    # construction succeeded despite the bad symbol
    with pytest.raises(UnsupportedSymbol):
        await feed.validate()


async def test_setup_resolves_subscription():
    feed = FakeExchange(symbols=['BTC-USD'], channels=[TRADES], config={'log': {'disabled': True}})
    feed.http_conn = FakeHTTP()
    assert dict(feed.subscription) == {}
    await feed.validate()
    assert feed.subscription == {'trades': ['BTCUSD']}
    assert feed.std_symbol_to_exchange_symbol('BTC-USD') == 'BTCUSD'
    assert feed.exchange_symbol_to_std_symbol('ETHUSD') == 'ETH-USD'


async def test_eager_resolution_when_already_loaded():
    await FakeExchange.load_symbols(conn=FakeHTTP())
    feed = FakeExchange(symbols=['BTC-USD'], channels=[TRADES], config={'log': {'disabled': True}})
    # mapping was already registered, so the feed is inspectable pre run
    assert feed.subscription == {'trades': ['BTCUSD']}


def test_sync_classmethods_outside_loop(monkeypatch):
    monkeypatch.setattr(FakeExchange, '_fetch_symbol_data', classmethod(
        lambda cls, conn, headers=None: _fake_fetch()))
    assert FakeExchange.symbols() == ['BTC-USD', 'ETH-USD']


async def _fake_fetch():
    import json
    return [json.loads(INSTRUMENTS)]


async def test_sync_classmethod_raises_inside_loop():
    with pytest.raises(RuntimeError, match='running event loop'):
        FakeExchange.symbol_mapping()


async def test_symbol_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    conn = FakeHTTP()
    await FakeExchange.load_symbols(conn=conn)
    assert (tmp_path / 'cryptofeed' / 'symbols' / 'FAKEX.json').exists()

    Symbols.clear()
    conn2 = FakeHTTP()
    syms = await FakeExchange.load_symbols(conn=conn2, cache_ttl=3600)
    assert syms == {'BTC-USD': 'BTCUSD', 'ETH-USD': 'ETHUSD'}
    assert conn2.requests == []

    # without a ttl the cache is ignored
    Symbols.clear()
    conn3 = FakeHTTP()
    await FakeExchange.load_symbols(conn=conn3)
    assert conn3.requests == ['https://fake.invalid/instruments']


async def test_symbol_cache_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    await FakeExchange.load_symbols(conn=FakeHTTP())
    cache_file = tmp_path / 'cryptofeed' / 'symbols' / 'FAKEX.json'
    stale = cache_file.read_text().replace('"timestamp":', '"timestamp_orig":')
    cache_file.write_text(stale.replace('{', '{"timestamp": 1.0, ', 1))

    Symbols.clear()
    conn = FakeHTTP()
    await FakeExchange.load_symbols(conn=conn, cache_ttl=3600)
    # cache was expired, so it fetched
    assert conn.requests == ['https://fake.invalid/instruments']
