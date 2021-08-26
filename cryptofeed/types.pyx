cdef class Trade:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly object amount
    cdef readonly str side
    cdef readonly str id
    cdef readonly str order_type
    cdef readonly double timestamp
    cdef readonly dict raw

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
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, bid, ask, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.bid = bid
        self.ask = ask
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'bid': self.side, 'ask': self.amount, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} bid: {self.bid} ask: {self.ask} timestamp: {self.timestamp}"
