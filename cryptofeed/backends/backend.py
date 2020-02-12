'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
from decimal import Decimal

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class BackendBookCallback:
    async def __call__(self, *, feed, pair, book, timestamp):
        data = {'timestamp': timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=self.numeric_type)
        await self.write(feed, pair, timestamp, data)


class BackendBookDeltaCallback:
    async def __call__(self, *, feed, pair, delta, timestamp):
        data = {'timestamp': timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)
        await self.write(feed, pair, timestamp, data)


class BackendTradeCallback:
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        data = {'feed': feed, 'pair': pair, 'timestamp': timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}
        if order_id:
            data['id'] = order_id
        await self.write(feed, pair, timestamp, data)


class BackendFundingCallback:
    async def __call__(self, *, feed, pair, **kwargs):
        if 'timestamp' in kwargs:
            timestamp = kwargs['timestamp']
        else:
            timestamp = time.time()
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])
        kwargs['feed'] = feed
        kwargs['pair'] = pair
        await self.write(feed, pair, timestamp, kwargs)


class BackendTickerCallback:
    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float):
        data = {'feed': feed, 'pair': pair, 'bid': self.numeric_type(bid), 'ask': self.numeric_type(ask), 'timestamp': timestamp}
        await self.write(feed, pair, timestamp, data)

        
class BackendOpenInterestCallback:
    async def __call__(self, *, feed, pair, open_interest, timestamp):
        data = {'feed': feed, 'pair': pair, 'open_interest': self.numeric_type(open_interest), 'timestamp': timestamp}
        await self.write(feed, pair, timestamp, data)
