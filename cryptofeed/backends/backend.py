'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time
from decimal import Decimal

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class Backend:
    def book(self, book: dict, timestamp: float, numeric_type) -> dict:
        data = {'timestamp': timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data, convert=numeric_type)
        return data

    def book_delta(self, delta: dict, timestamp: float, numeric_type) -> dict:
        data = {'timestamp': timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data, convert=numeric_type)
        return data

    def trade(self, feed: str, pair: str, side: str, amount: str, price: Decimal, order_id, timestamp, numeric_type) -> dict:
        return  {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                 'side': side, 'amount': self.numeric_type(amount), 'price': self.numeric_type(price)}

    def funding(self, numeric_type, data: dict) -> dict:
        for key in data:
            if isinstance(data[key], Decimal):
                data[key] = numeric_type(data[key])
        return data
    
    def ticker(self, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float, numeric_type) -> dict:
        return {'feed': feed, 'pair': pair, 'bid': self.numeric_type(bid), 'ask': self.numeric_type(ask), 'timestamp': timestamp}
