'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import json
from unittest.mock import patch

from cryptofeed.defines import ASK, BID, BITSTAMP
from cryptofeed.exchanges.bitstamp import Bitstamp


class FakeHTTPConnection:
    def __init__(self, response):
        self.response = response

    async def read(self, url):
        assert url.endswith('/btcusd')
        return json.dumps(self.response)


def make_bitstamp(callback):
    feed = Bitstamp.__new__(Bitstamp)
    feed.id = BITSTAMP
    feed.max_depth = 0
    feed.exchange_symbol_mapping = {'btcusd': 'BTC-USD'}
    feed.ignore_invalid_instruments = False
    feed._l2_book = {}
    feed.last_update_id = {}
    feed.book_callback = callback
    feed.rest_endpoints = Bitstamp.rest_endpoints
    feed.sandbox = False
    return feed


def test_bitstamp_l2_snapshot_watermark_uses_microtimestamp():
    callbacks = []

    async def callback(*args, **kwargs):
        callbacks.append((args, kwargs))

    snapshot = {
        'timestamp': '1000',
        'microtimestamp': '1000000123456',
        'bids': [['100', '1']],
        'asks': [['101', '2']],
    }
    feed = make_bitstamp(callback)
    feed.http_conn = FakeHTTPConnection(snapshot)

    async def no_sleep(_):
        pass

    with patch('cryptofeed.exchanges.bitstamp.asyncio.sleep', new=no_sleep):
        asyncio.run(feed._snapshot(['btcusd'], None))

    assert feed.last_update_id == {'BTC-USD': 1000000123456}
    assert len(callbacks) == 1

    def delta(microtimestamp, size):
        return {
            'event': 'data',
            'channel': 'diff_order_book_btcusd',
            'data': {
                'timestamp': '1000',
                'microtimestamp': str(microtimestamp),
                'bids': [['100', size]],
                'asks': [],
            },
        }

    async def process(message):
        await feed._process_l2_book(message, 1000.0)

    # All three updates are in the same second as the snapshot. Only their
    # microsecond ordering can distinguish stale/equal updates from a new one.
    asyncio.run(process(delta(1000000123455, '2')))
    asyncio.run(process(delta(1000000123456, '2')))
    assert len(callbacks) == 1
    assert feed.last_update_id == {'BTC-USD': 1000000123456}
    assert feed._l2_book['BTC-USD'].book[BID][Decimal('100')] == Decimal('1')

    asyncio.run(process(delta(1000000123457, '3')))
    assert len(callbacks) == 2
    assert feed.last_update_id == {}
    assert feed._l2_book['BTC-USD'].book[BID][Decimal('100')] == Decimal('3')
    assert feed._l2_book['BTC-USD'].book[ASK][Decimal('101')] == Decimal('2')
