'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
import json
import itertools

from cryptofeed.backends.http import HTTPCallback
from cryptofeed.backends._util import book_flatten
from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback, BackendOpenInterestCallback


LOG = logging.getLogger('feedhandler')


class ElasticCallback(HTTPCallback):
    def __init__(self, addr: str, index=None, numeric_type=str, **kwargs):
        super().__init__(addr, **kwargs)
        index = index if index else self.default_index
        self.addr = f"{addr}/{index}/{index}"
        self.session = None
        self.numeric_type = numeric_type

    async def write(self, feed, pair, timestamp, data):
        await self.http_write('POST', json.dumps(data), headers={'content-type': 'application/json'})

    async def write_bulk(self, data):
        data = itertools.chain(*zip([json.dumps({ "index":{} })] * len(data), [json.dumps(d) for d in data]))
        data = '\n'.join(data)
        data = f"{data}\n"
        await self.http_write('POST', data, headers={'content-type': 'application/x-ndjson'})


class TradeElastic(ElasticCallback, BackendTradeCallback):
    default_index = 'trades'


class FundingElastic(ElasticCallback, BackendFundingCallback):
    default_index = 'funding'


class BookElastic(ElasticCallback, BackendBookCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def write(self, feed, pair, timestamp, data):
        data = book_flatten(feed, pair, data, timestamp, False)
        await self.write_bulk(data)


class BookDeltaElastic(ElasticCallback, BackendBookDeltaCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def write(self, feed, pair, timestamp, data):
        data = book_flatten(feed, pair, data, timestamp, True)
        await self.write_bulk(data)


class TickerElastic(ElasticCallback, BackendTickerCallback):
    default_index = 'ticker'


class OpenInterestElastic(ElasticCallback, BackendOpenInterestCallback):
    default_index = 'open_interest'
