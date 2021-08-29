'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
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

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': self.amount, 'price': self.price, 'id': self.id, 'order_type': self.order_type, 'timestamp': self.timestamp}

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

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'bid': self.bid, 'ask': self.ask, 'timestamp': self.timestamp}

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
    cdef readonly double timestamp
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

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'leaves_qty': self.leaves_qty, 'price': self.price, 'id': self.id, 'status': self.status, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"'exchange: {self.exchange} symbol: {self.symbol} side: {self.side} leaves_qty: {self.leaves_qty} price: {self.price} id: {self.id} status: {self.status} timestamp: {self.timestamp}"


cdef class Funding:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object mark_price
    cdef readonly object rate
    cdef readonly double next_funding_time
    cdef readonly object predicted_rate
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, mark_price, rate, next_funding_time, timestamp, predicted_rate=None, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.mark_price = mark_price
        self.rate = rate
        self.predicted_rate = predicted_rate
        self.next_funding_time = next_funding_time
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'mark_price': self.mark_price, 'rate': self.rate, 'next_funding_time': self.next_funding_time, 'predicted_rate': self.predicted_rate, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"'exchange: {self.exchange} symbol: {self.symbol} mark_price: {self.mark_price} rate: {self.rate} next_funding_time: {self.next_funding_time} predicted_rate: {self.predicted_rate} timestamp: {self.timestamp}"


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
    cdef readonly dict raw

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

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'start': self.start, 'stop': self.stop, 'interval': self.interval, 'trades': self.trades, 'open': self.open, 'close': self.close, 'high': self.high, 'low': self.low, 'volume' : self.volume, 'closed': self.closed, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"'exchange: {self.exchange} symbol: {self.symbol} start: {self.start} stop: {self.stop} interval: {self.interval} trades: {self.trades} open: {self.open} close: {self.close} high: {self.high} low: {self.low} volume: {self.volume} closed: {self.closed} timestamp: {self.timestamp}"


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

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'price': self.price, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} price: {self.price} timestamp: {self.timestamp}"


cdef class OpenInterest:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object open_interest
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, open_interest, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.open_interest = open_interest
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'open_interest': self.open_interest, 'timestamp': self.timestamp}

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

    def __init__(self, exchange, symbol, bids=None, asks=None, max_depth=0):
        self.exchange = exchange
        self.symbol = symbol
        self.book = _OrderBook(max_depth=max_depth)
        if bids:
            self.book.bids = bids
        if asks:
            self.book.asks = asks
        self.delta = None
        self.timestamp = None
        self.sequence_number = None
        self.checksum = None
        self.raw = None

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'book': self.book, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} book: {self.book} timestamp: {self.timestamp}"
