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


LOG = logging.getLogger('feedhandler')


class ElasticCallback(HTTPCallback):
    def __init__(self, addr: str, index=None, numeric_type=str, **kwargs):
        super().__init__(addr, **kwargs)
        index = index if index else self.default_index
        self.addr = f"{addr}/{index}/{index}"
        self.session = None
        self.numeric_type = numeric_type
    
    async def post(self, data):
        await self.write('POST', json.dumps(data), headers={'content-type': 'application/json'})

    async def post_bulk(self, data):
        data = itertools.chain(*zip([json.dumps({ "index":{} })] * len(data), [json.dumps(d) for d in data]))
        data = '\n'.join(data)
        data = f"{data}\n"
        await self.write('POST', data, headers={'content-type': 'application/x-ndjson'})


class TradeElastic(ElasticCallback):
    default_index = 'trades'

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        if order_id is None:
            order_id = 'None'

        trade = self.trade(feed, pair, side, amount, price, order_id, timestamp, self.numeric_type)
        await self.post(trade)


class FundingElastic(ElasticCallback):
    default_index = 'funding'

    async def __call__(self, *, feed, pair, **kwargs):
        data = self.funding(self.numeric_type, kwargs)
        await self.write('POST', json.dumps(data), headers={'content-type': 'application/json'})


class BookElastic(ElasticCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def __call__(self, *, feed, pair, book, timestamp):
        data = self.book(book, timestamp, self.numeric_type)
        data = book_flatten(feed, pair, data, timestamp, False)
        await self.post_bulk(data)


class BookDeltaElastic(ElasticCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def __call__(self, *, feed, pair, delta, timestamp):
        self.book_delta(delta, timestamp, self.numeric_type)
        data = book_flatten(feed, pair, data, timestamp, True)
        await self.post_bulk(data)
