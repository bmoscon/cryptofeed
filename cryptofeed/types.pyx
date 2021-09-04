'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BID, ASK
from order_book import OrderBook as _OrderBook


cdef class Trade:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly object amount
    cdef readonly str side
    cdef readonly str id
    cdef readonly str order_type
    cdef readonly double timestamp
    cdef readonly object raw # can be dict or list

    def __init__(self, exchange, symbol, side, amount, price, timestamp, id=None, order_type=None, raw=None):
        self.price = price
        self.amount = amount
        self.symbol = symbol
        self.side = side
        self.id = id
        self.timestamp = timestamp
        self.exchange = exchange
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': self.amount, 'price': self.price, 'id': self.id, 'order_type': self.order_type, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': as_type(self.amount), 'price': as_type(self.price), 'id': self.id, 'order_type': self.order_type, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} side: {self.side} amount: {self.amount} price: {self.price} id: {self.id} order_type: {self.order_type} timestamp: {self.timestamp}"


cdef class Ticker:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object bid
    cdef readonly object ask
    cdef readonly object timestamp
    cdef readonly object raw

    def __init__(self, exchange, symbol, bid, ask, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'bid': self.bid, 'ask': self.ask, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'bid': as_type(self.bid), 'ask': as_type(self.ask), 'timestamp': self.timestamp}
        

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} bid: {self.bid} ask: {self.ask} timestamp: {self.timestamp}"


cdef class Liquidation:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly str side
    cdef readonly object leaves_qty
    cdef readonly object price
    cdef readonly str id
    cdef readonly str status
    cdef readonly object timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, side, leaves_qty, price, id, status, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.leaves_qty = leaves_qty
        self.price = price
        self.id = id
        self.status = status
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'leaves_qty': self.leaves_qty, 'price': self.price, 'id': self.id, 'status': self.status, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'leaves_qty': as_type(self.leaves_qty), 'price': as_type(self.price), 'id': self.id, 'status': self.status, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} side: {self.side} leaves_qty: {self.leaves_qty} price: {self.price} id: {self.id} status: {self.status} timestamp: {self.timestamp}"


cdef class Funding:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object mark_price
    cdef readonly object rate
    cdef readonly object next_funding_time  # can be missing/None
    cdef readonly object predicted_rate
    cdef readonly double timestamp
    cdef readonly object raw

    def __init__(self, exchange, symbol, mark_price, rate, next_funding_time, timestamp, predicted_rate=None, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.mark_price = mark_price
        self.rate = rate
        self.predicted_rate = predicted_rate
        self.next_funding_time = next_funding_time
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'mark_price': self.mark_price, 'rate': self.rate, 'next_funding_time': self.next_funding_time, 'predicted_rate': self.predicted_rate, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'mark_price': as_type(self.mark_price) if self.mark_price else None, 'rate': self.rate, 'next_funding_time': self.next_funding_time, 'predicted_rate': as_type(self.predicted_rate) if self.predicted_rate else None, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} mark_price: {self.mark_price} rate: {self.rate} next_funding_time: {self.next_funding_time} predicted_rate: {self.predicted_rate} timestamp: {self.timestamp}"


cdef class Candle:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly double start
    cdef readonly double stop
    cdef readonly str interval
    cdef readonly object trades # None or int
    cdef readonly object open
    cdef readonly object close
    cdef readonly object high
    cdef readonly object low
    cdef readonly object volume
    cdef readonly bint closed
    cdef readonly object timestamp # None or float
    cdef readonly object raw # dict or list

    def __init__(self, exchange, symbol, start, stop, interval, trades, open, close, high, low, volume, closed, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.start = start
        self.stop = stop
        self.interval = interval
        self.trades = trades
        self.open = open
        self.close = close
        self.high = high
        self.low = low
        self.volume = volume
        self.closed = closed
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'start': self.start, 'stop': self.stop, 'interval': self.interval, 'trades': self.trades, 'open': self.open, 'close': self.close, 'high': self.high, 'low': self.low, 'volume' : self.volume, 'closed': self.closed, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'start': self.start, 'stop': self.stop, 'interval': self.interval, 'trades': self.trades, 'open': as_type(self.open), 'close': as_type(self.close), 'high': as_type(self.high), 'low': as_type(self.low), 'volume' : as_type(self.volume), 'closed': self.closed, 'timestamp': self.timestamp}


    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} start: {self.start} stop: {self.stop} interval: {self.interval} trades: {self.trades} open: {self.open} close: {self.close} high: {self.high} low: {self.low} volume: {self.volume} closed: {self.closed} timestamp: {self.timestamp}"


cdef class Index:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, price, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.price = price
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'price': self.price, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'price': as_type(self.price), 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} price: {self.price} timestamp: {self.timestamp}"


cdef class OpenInterest:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object open_interest
    cdef readonly object timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, open_interest, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.open_interest = open_interest
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'open_interest': self.open_interest, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'open_interest': as_type(self.open_interest), 'timestamp': self.timestamp}


    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} open_interest: {self.open_interest} timestamp: {self.timestamp}"


cdef class OrderBook:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object book
    cdef public dict delta
    cdef public object sequence_number
    cdef public object checksum
    cdef public object timestamp
    cdef public object raw  # Can be dict or list

    def __init__(self, exchange, symbol, bids=None, asks=None, max_depth=0, checksum_format=None):
        self.exchange = exchange
        self.symbol = symbol
        self.book = _OrderBook(max_depth=max_depth, checksum_format=checksum_format)
        if bids:
            self.book.bids = bids
        if asks:
            self.book.asks = asks
        self.delta = None
        self.timestamp = None
        self.sequence_number = None
        self.checksum = None
        self.raw = None

    cpdef dict to_dict(self, delta=False, as_type=None):
        if delta:
            if as_type is None:
                return {'exchange': self.exchange, 'symbol': self.symbol, 'delta': self.delta, 'timestamp': self.timestamp}
            return {'exchange': self.exchange, 'symbol': self.symbol, 'delta': {BID: [(as_type(price), as_type(size)) for price, size in self.delta[BID]], ASK: [(as_type(price), as_type(size)) for price, size in self.delta[ASK]]} if self.delta else None, 'timestamp': self.timestamp}

        book_dict = self.book.to_dict()
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'book': book_dict, 'delta': self.delta, 'timestamp': self.timestamp}
        ret = {BID: {as_type(price): as_type(size) for price, size in book_dict[BID].items()}, ASK: {as_type(price): as_type(size) for price, size in book_dict[ASK].items()}}
        delta = {BID: [(as_type(price), as_type(size)) for price, size in self.delta[BID]], ASK: [(as_type(price), as_type(size)) for price, size in self.delta[ASK]]} if self.delta else None
        return {'exchange': self.exchange, 'symbol': self.symbol, 'book': ret, 'delta': delta, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} book: {self.book} timestamp: {self.timestamp}"


cdef class OrderInfo:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly str id
    cdef readonly str side
    cdef readonly str status
    cdef readonly str type
    cdef readonly object price
    cdef readonly object amount
    cdef readonly object remaining
    cdef readonly object timestamp
    cdef public object raw  # Can be dict or list

    def __init__(self, exchange, symbol, id, side, status, type, price, amount, remaining, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.id = id
        self.side = side
        self.status = status
        self.type = type
        self.price = price
        self.amount = amount
        self.remaining = remaining
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol,  'id': self.id, 'side': self.side, 'status': self.status, 'type': self.type, 'price': self.price, 'amount': self.amount, 'remaining': self.remaining, 'timestamp': self.timestamp}
    
    def __repr__(self):
        return f'exchange: {self.exchange} symbol: {self.symbol}  id: {self.id} side: {self.side} status: {self.status} type: {self.type} price: {self.price} amount: {self.amount} remaining: {self.remaining} timestamp: {self.timestamp}'
