'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed.backends._util import book_convert, book_delta_convert
from cryptofeed.defines import BID, ASK


class BackendBookCallback:
    async def __call__(self, *, feed: str, symbol: str, book: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=self.numeric_type)
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendBookDeltaCallback:
    async def __call__(self, *, feed: str, symbol: str, delta: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=self.numeric_type)
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendTradeCallback:
    async def __call__(self, *, feed: str, symbol: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, receipt_timestamp: float, order_type: str = None):
        data = {'feed': feed, 'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}
        if order_id:
            data['id'] = order_id
        if order_type:
            data['order_type'] = order_type
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendFundingCallback:
    async def __call__(self, *, feed, symbol, **kwargs):
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = self.numeric_type(kwargs[key])
        kwargs['feed'] = feed
        kwargs['symbol'] = symbol
        timestamp = kwargs.get('timestamp')
        receipt_timestamp = kwargs.get('receipt_timestamp')

        await self.write(feed, symbol, timestamp, receipt_timestamp, kwargs)


class BackendTickerCallback:
    async def __call__(self, *, feed: str, symbol: str, bid: Decimal, ask: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'bid': self.numeric_type(bid), 'ask': self.numeric_type(ask), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendOpenInterestCallback:
    async def __call__(self, *, feed: str, symbol: str, open_interest: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'open_interest': self.numeric_type(open_interest), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendFuturesIndexCallback:
    async def __call__(self, *, feed: str, symbol: str, futures_index: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'futures_index': self.numeric_type(futures_index), 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendLiquidationsCallback:
    async def __call__(self, *, feed: str, symbol: str, side: str, leaves_qty: Decimal, price: Decimal, order_id: str, timestamp: float, receipt_timestamp: float):
        data = {'feed': feed, 'symbol': symbol, 'side': side, 'leaves_qty': self.numeric_type(leaves_qty), 'price': self.numeric_type(price), 'order_id': order_id if order_id else "None", 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(feed, symbol, timestamp, receipt_timestamp, data)


class BackendMarketInfoCallback:
    async def __call__(self, *, feed: str, symbol: str, timestamp: float, **kwargs):
        kwargs['feed'] = feed
        kwargs['symbol'] = symbol
        kwargs['timestamp'] = timestamp
        await self.write(feed, symbol, timestamp, timestamp, kwargs)


class BackendTransactionsCallback:
    async def __call__(self, *, feed: str, symbol: str, timestamp: float, **kwargs):
        kwargs['feed'] = feed
        kwargs['symbol'] = symbol
        kwargs['timestamp'] = timestamp
        await self.write(feed, symbol, timestamp, timestamp, kwargs)
