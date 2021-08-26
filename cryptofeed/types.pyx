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
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, mark_price, rate, next_funding_time, timestamp, raw=None):
        self.exchange = exchange
        self.symbol = symbol
        self.mark_price = mark_price
        self.rate = rate
        self.next_funding_time = next_funding_time
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self):
        return {'exchange': self.exchange, 'symbol': self.symbol, 'mark_price': self.mark_price, 'rate': self.rate, 'next_funding_time': self.next_funding_time, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"'exchange: {self.exchange} symbol: {self.symbol} mark_price: {self.mark_price} rate: {self.rate} next_funding_time: {self.next_funding_time} timestamp: {self.timestamp}"


cdef class Candle:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly double start
    cdef readonly double stop
    cdef readonly str interval
    cdef readonly unsigned int trades
    cdef readonly object open
    cdef readonly object close
    cdef readonly object high
    cdef readonly object low
    cdef readonly object volume
    cdef readonly bint closed
    cdef readonly double timestamp
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
