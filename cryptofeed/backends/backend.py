'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
from decimal import Decimal

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class BackendBookCallback:
    async def __call__(self, *, feed: str, pair: str, book: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=self.numeric_type)
        await self.write(feed, pair, timestamp, receipt_timestamp, data)


class BackendBookDeltaCallback:
    async def __call__(self, *, feed: str, pair: str, delta: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)
        await self.write(feed, pair, timestamp, receipt_timestamp, data)


class BackendTradeCallback:
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'pair': pair, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}
        if order_id:
            data['id'] = order_id
        await self.write(feed, pair, timestamp, receipt_timestamp, data)


class BackendFundingCallback:
    async def __call__(self, *, feed, pair, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])
        kwargs['feed'] = feed
        kwargs['pair'] = pair
        timestamp = kwargs.get('timestamp')
        receipt_timestamp = kwargs.get('receipt_timestamp')

        await self.write(feed, pair, timestamp, receipt_timestamp, kwargs)


class BackendTickerCallback:
    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'pair': pair, 'bid': self.numeric_type(bid), 'ask': self.numeric_type(ask), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, pair, timestamp, receipt_timestamp, data)

        
class BackendOpenInterestCallback:
    async def __call__(self, *, feed: str, pair: str, open_interest: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'pair': pair, 'open_interest': self.numeric_type(open_interest), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, pair, timestamp, receipt_timestamp, data)
