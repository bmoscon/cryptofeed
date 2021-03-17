'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import itertools
import logging
from datetime import datetime as dt
from datetime import timezone as tz

from yapic import json

from cryptofeed.backends._util import book_flatten
from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)
from cryptofeed.backends.http import HTTPCallback


LOG = logging.getLogger('feedhandler')


class ElasticCallback(HTTPCallback):
    def __init__(self, addr: str, index=None, numeric_type=str, **kwargs):
        super().__init__(addr, **kwargs)
        index = index if index else self.default_index
        self.addr = f"{addr}/{index}/{index}"
        self.session = None
        self.numeric_type = numeric_type

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        if 'timestamp' in data:
            data['timestamp'] = f"{dt.fromtimestamp(data['timestamp'], tz=tz.utc).isoformat()}Z"
        if 'receipt_timestamp' in data:
            data['receipt_timestamp'] = f"{dt.fromtimestamp(data['receipt_timestamp'], tz=tz.utc).isoformat()}Z"

        await self.queue.put({'data': json.dumps(data), 'headers': {'content-type': 'application/json'}})

    async def write_bulk(self, data):
        data = itertools.chain(*zip([json.dumps({"index": {}})] * len(data), [json.dumps(d) for d in data]))
        data = '\n'.join(data)
        data = f"{data}\n"
        await self.queue.put({'data': data, 'headers': {'content-type': 'application/x-ndjson'}})


class TradeElastic(ElasticCallback, BackendTradeCallback):
    default_index = 'trades'


class FundingElastic(ElasticCallback, BackendFundingCallback):
    default_index = 'funding'


class BookElastic(ElasticCallback, BackendBookCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        if 'timestamp' in data:
            data['timestamp'] = f"{dt.fromtimestamp(data['timestamp'], tz=tz.utc).isoformat()}Z"
        if 'receipt_timestamp' in data:
            data['receipt_timestamp'] = f"{dt.fromtimestamp(data['receipt_timestamp'], tz=tz.utc).isoformat()}Z"
        timestamp = f"{dt.fromtimestamp(timestamp, tz=tz.utc).isoformat()}Z"
        receipt_timestamp = F"{dt.fromtimestamp(receipt_timestamp, tz=tz.utc).isoformat()}Z"

        data = book_flatten(feed, symbol, data, timestamp, False)
        await self.write_bulk(data)


class BookDeltaElastic(ElasticCallback, BackendBookDeltaCallback):
    default_index = 'book'

    def __init__(self, *args, index='book', **kwargs):
        super().__init__(*args, index=index, **kwargs)
        self.addr = f"{self.addr}/_bulk"

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        if 'timestamp' in data:
            data['timestamp'] = f"{dt.fromtimestamp(data['timestamp'], tz=tz.utc).isoformat()}Z"
        if 'receipt_timestamp' in data:
            data['receipt_timestamp'] = f"{dt.fromtimestamp(data['receipt_timestamp'], tz=tz.utc).isoformat()}Z"
        timestamp = f"{dt.fromtimestamp(timestamp, tz=tz.utc).isoformat()}Z"
        receipt_timestamp = F"{dt.fromtimestamp(receipt_timestamp, tz=tz.utc).isoformat()}Z"

        data = book_flatten(feed, symbol, data, timestamp, True)
        await self.write_bulk(data)


class TickerElastic(ElasticCallback, BackendTickerCallback):
    default_index = 'ticker'


class OpenInterestElastic(ElasticCallback, BackendOpenInterestCallback):
    default_index = 'open_interest'


class LiquidationsElastic(ElasticCallback, BackendLiquidationsCallback):
    default_index = 'liquidations'


class MarketInfoElastic(ElasticCallback, BackendMarketInfoCallback):
    default_index = 'market_info'


class TransactionsElastic(ElasticCallback, BackendTransactionsCallback):
    default_index = 'transactions'


class CandlesElastic(ElasticCallback, BackendCandlesCallback):
    default_index = 'candles'
