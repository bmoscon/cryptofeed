'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import json
import itertools

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert, book_flatten
from cryptofeed.backends.http import HTTPCallback
from cryptofeed.exceptions import UnsupportedType


LOG = logging.getLogger('feedhandler')


class ElasticCallback(HTTPCallback):
    def __init__(self, addr: str, index=None, numeric_type=str, **kwargs):
        super().__init__(addr, **kwargs)
        self.addr = f"{addr}/{index}/{index}"
        self.session = None
        self.numeric_type = numeric_type


class TradeElastic(ElasticCallback):
    def __init__(self, *args, index='trades', **kwargs):
        super().__init__(*args, index=index, **kwargs)

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        if order_id is None:
            order_id = 'None'

        trade = {
            'pair': pair,
            'side': side,
            'id': order_id,
            'amount': self.numeric_type(amount),
            'price': self.numeric_type(price),
            'timestamp': timestamp
        }
        await self.write('POST', json.dumps(trade), headers={'content-type': 'application/json'})


class FundingElastic(ElasticCallback):
    def __init__(self, *args, index='funding', **kwargs):
        super().__init__(*args, index=index, **kwargs)

    async def __call__(self, *, feed, pair, **kwargs):
        data = {}
        for key, val in kwargs.items():
            if isinstance(val, (Decimal, float)):
                val = self.numeric_type(val)
            data[key] = val

        await self.write('POST', json.dumps(data), headers={'content-type': 'application/json'})


class BookElastic(ElasticCallback):
    def __init__(self, *args, index='book', depth=None, **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.depth = depth
        self.previous = {BID: {}, ASK: {}}
        self.addr = f"{self.addr}/_bulk"

    async def __call__(self, *, feed, pair, book, timestamp):
        data = {BID: {}, ASK: {}}
        book_convert(book, data, self.depth, convert=self.numeric_type)

        if self.depth:
            if data[BID] == self.previous[BID] and data[ASK] == self.previous[ASK]:
                return
            self.previous[ASK] = data[ASK]
            self.previous[BID] = data[BID]
        data = book_flatten(feed, pair, data, timestamp, False)

        data = itertools.chain(*zip([json.dumps({ "index":{} })] * len(data), [json.dumps(d) for d in data]))
        data = '\n'.join(data)
        data = f"{data}\n"

        await self.write('POST', data, headers={'content-type': 'application/x-ndjson'})


class BookDeltaElastic(ElasticCallback):
    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def __call__(self, *, feed, pair, delta, timestamp):
        data = {BID: {}, ASK: {}}

        book_delta_convert(delta, data, convert=self.numeric_type)
        data = book_flatten(feed, pair, data, timestamp, True)

        data = itertools.chain(*zip([json.dumps({ "index":{} })] * len(data), [json.dumps(d) for d in data]))
        data = '\n'.join(data)
        data = f"{data}\n"

        await self.write('POST', data, headers={'content-type': 'application/x-ndjson'})
