cdef class Trade:
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly object amount
    cdef readonly str side
    cdef readonly str id
    cdef readonly str order_type
    cdef readonly double timestamp
    cdef readonly str exchange

    def __init__(self, exchange, symbol, side, amount, price, timestamp, id=None, order_type=None):
        self.price = price
        self.amount = amount
        self.symbol = symbol
        self.side = side
        self.id = id
        self.timestamp = timestamp
        self.exchange = exchange

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': self.amount, 'price': self.price, 'id': self.id, 'order_type': self.order_type, 'timestamp': self.timestamp}
