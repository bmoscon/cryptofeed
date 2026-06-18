'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import pytest
from yapic import json

from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase
from cryptofeed.symbols import Symbols


class HTTPSyncStub:
    def __init__(self):
        self.calls = []

    def read(self, address: str, params=None, headers=None, json=False, text=True, uuid=None):
        self.calls.append({'address': address, 'headers': headers})
        return {
            'products': [
                {
                    'base_currency_id': 'BTC',
                    'quote_currency_id': 'USD',
                    'quote_increment': '0.01',
                    'product_id': 'BTC-USD'
                }
            ]
        }


class RecordingConnection:
    def __init__(self):
        self.messages = []

    async def write(self, msg: str):
        self.messages.append(json.loads(msg))


@pytest.fixture(autouse=True)
def clear_symbols():
    Symbols.clear()
    yield
    Symbols.clear()


def _set_coinbase_symbols():
    Symbols.set(Coinbase.id, {'BTC-USD': 'BTC-USD'}, {'tick_size': {'BTC-USD': '0.01'}, 'instrument_type': {'BTC-USD': 'spot'}})


def test_symbols_use_public_market_products_without_credentials(monkeypatch):
    http_sync = HTTPSyncStub()
    monkeypatch.setattr(Coinbase, 'http_sync', http_sync)

    assert Coinbase.symbols(config={}, refresh=True) == ['BTC-USD']
    assert http_sync.calls == [{'address': 'https://api.coinbase.com/api/v3/brokerage/market/products', 'headers': None}]


def test_subscribe_omits_auth_fields_without_credentials():
    _set_coinbase_symbols()
    feed = Coinbase(symbols=['BTC-USD'], channels=[TRADES], config={})
    conn = RecordingConnection()

    asyncio.run(feed.subscribe(conn))

    assert conn.messages == [
        {'type': 'subscribe', 'product_ids': ['BTC-USD'], 'channel': 'market_trades'},
        {'type': 'subscribe', 'product_ids': ['BTC-USD'], 'channel': 'heartbeats'}
    ]


def test_subscribe_keeps_auth_fields_when_credentials_are_configured():
    _set_coinbase_symbols()
    feed = Coinbase(
        symbols=['BTC-USD'],
        channels=[TRADES],
        config={'coinbase': {'key_id': 'test-key', 'key_secret': 'test-secret'}}
    )
    conn = RecordingConnection()

    asyncio.run(feed.subscribe(conn))

    for message in conn.messages:
        assert message['api_key'] == 'test-key'
        assert 'timestamp' in message
        assert 'signature' in message
