'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed.backends._util import book_convert, book_delta_convert
from cryptofeed.defines import BID, ASK


class BackendBookCallback:
#Orderbook in dictionary form. Specifically, self._call_(book: dict).
    async def __call__(self, *, symbol: str, book: dict, timestamp: float, receipt_timestamp: float):
        data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=self.numeric_type)
        await self.write(symbol, timestamp, receipt_timestamp, data)
#modified

class BackendBookDeltaCallback:
    async def __call__(self, *, symbol: str, book:dict, forced:bool, delta: dict, timestamp: float, receipt_timestamp: float):
        if delta is not None:
            data = {'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, BID: {}, ASK: {}}
            book_delta_convert(delta, data, convert=self.numeric_type)
        else:
            data=delta
        await self.write(symbol, timestamp, receipt_timestamp, forced, book, data)
#modified

class BackendTradeCallback:
    async def __call__(self, *, symbol: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp: float, tick_direction=None, receipt_timestamp: float, order_type: str = None):
        data = {'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp,
                'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}
        if tick_direction:
            data['tick_direction']=tick_direction
        if order_id:
            data['id'] = order_id
        if order_type:
            data['order_type'] = order_type
        await self.write(symbol, timestamp, receipt_timestamp, data)
#modified


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
    async def __call__(self, *, symbol: str, bid: Decimal, ask: Decimal, timestamp: float, bid_size: float, ask_size: float, receipt_timestamp: float):
        data = {'symbol': symbol, 'bid': self.numeric_type(bid), 'bid_size':self.numeric_type(bid_size),
            'ask': self.numeric_type(ask), 'ask_size': self.numeric_type(ask_size), 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp}
        await self.write(symbol, timestamp, receipt_timestamp, data)
#modified


class BackendOpenInterestCallback:
    async def __call__(self, *, symbol: str, open_interest: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'symbol': symbol, 'open_interest': self.numeric_type(open_interest), 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp}
        await self.write(symbol, timestamp, receipt_timestamp, data)


class BackendFuturesIndexCallback:
    async def __call__(self, *, symbol: str, futures_index: Decimal, timestamp: float, receipt_timestamp: float):
        data = {'symbol': symbol, 'futures_index': self.numeric_type(futures_index), 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp}
        await self.write(symbol, timestamp, receipt_timestamp, data)


class BackendLiquidationsCallback:
    async def __call__(self, *, symbol: str, side: str, leaves_qty: Decimal, price: Decimal, order_id: str, timestamp: float, receipt_timestamp: float):
        data = {'symbol': symbol, 'side': side, 'leaves_qty': self.numeric_type(leaves_qty), 'price': self.numeric_type(price), 'order_id': order_id if order_id else "None", 'receipt_timestamp': receipt_timestamp, 'timestamp': timestamp}
        await self.write(symbol, timestamp, receipt_timestamp, data)


class BackendMarketInfoCallback:
    async def __call__(self, *, symbol: str, timestamp: float, **kwargs):
        kwargs['symbol'] = symbol
        kwargs['timestamp'] = timestamp
        await self.write(symbol, timestamp, timestamp, kwargs)


class BackendTransactionsCallback:
    async def __call__(self, *, symbol: str, timestamp: float, **kwargs):
        kwargs['symbol'] = symbol
        kwargs['timestamp'] = timestamp
        await self.write(symbol, timestamp, timestamp, kwargs)


class BackendOrderBookCallback:
#Orderbook in list form. Specifically, self._call_(bid: list, ask: list).  
    async def __call__(self, *, symbol:str, timestamp: float, bid: list, ask: list, receipt_timestamp: float):
        data={'symbol': symbol, 'timestamp': timestamp, 'receipt_timestamp': receipt_timestamp, 'bid': bid, 'ask': ask}
        await self.write(symbol, timestamp, receipt_timestamp, data)
#modified
