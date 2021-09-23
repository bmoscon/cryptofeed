'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed.defines import BID, ASK
from order_book import OrderBook as _OrderBook


cdef class Trade:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly object amount
    cdef readonly str side
    cdef readonly str id
    cdef readonly str type
    cdef readonly double timestamp
    cdef readonly object raw  # can be dict or list

    def __init__(self, exchange, symbol, side, amount, price, timestamp, id=None, type=None, raw=None):
        assert isinstance(price, Decimal)
        assert isinstance(amount, Decimal)

        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.price = price
        self.timestamp = timestamp
        self.id = id
        self.type = type
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': self.amount, 'price': self.price, 'id': self.id, 'type': self.type, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': as_type(self.amount), 'price': as_type(self.price), 'id': self.id, 'type': self.type, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} side: {self.side} amount: {self.amount} price: {self.price} id: {self.id} type: {self.type} timestamp: {self.timestamp}"

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.price == cmp.price and self.amount == cmp.amount and self.side == cmp.side and self.id == cmp.id and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Ticker:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object bid
    cdef readonly object ask
    cdef readonly object timestamp
    cdef readonly object raw

    def __init__(self, exchange, symbol, bid, ask, timestamp, raw=None):
        assert isinstance(bid, Decimal)
        assert isinstance(ask, Decimal)
        assert timestamp is None or isinstance(timestamp, float)

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

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.bid == cmp.bid and self.ask == cmp.ask and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


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
        assert isinstance(leaves_qty, Decimal)
        assert isinstance(price, Decimal)
        assert timestamp is None or isinstance(timestamp, float)

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

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.side == cmp.side and self.leaves_qty == cmp.leaves_qty and self.price == cmp.price and self.id == cmp.id and self.status == cmp.status and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())

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
        assert mark_price is None or isinstance(mark_price, Decimal)
        assert isinstance(rate, Decimal)
        assert next_funding_time is None or isinstance(next_funding_time, float)
        assert predicted_rate is None or isinstance(predicted_rate, Decimal)

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

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.mark_price == cmp.mark_price and self.rate == cmp.rate and self.next_funding_time == cmp.next_funding_time and self.predicted_rate == cmp.predicted_rate and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Candle:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly double start
    cdef readonly double stop
    cdef readonly str interval
    cdef readonly object trades  # None or int
    cdef readonly object open
    cdef readonly object close
    cdef readonly object high
    cdef readonly object low
    cdef readonly object volume
    cdef readonly bint closed
    cdef readonly object timestamp  # None or float
    cdef readonly object raw  # dict or list

    def __init__(self, exchange, symbol, start, stop, interval, trades, open, close, high, low, volume, closed, timestamp, raw=None):
        assert trades is None or isinstance(trades, int)
        assert isinstance(open, Decimal)
        assert isinstance(close, Decimal)
        assert isinstance(high, Decimal)
        assert isinstance(low, Decimal)
        assert isinstance(volume, Decimal)
        assert timestamp is None or isinstance(timestamp, float)

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
            return {'exchange': self.exchange, 'symbol': self.symbol, 'start': self.start, 'stop': self.stop, 'interval': self.interval, 'trades': self.trades, 'open': self.open, 'close': self.close, 'high': self.high, 'low': self.low, 'volume': self.volume, 'closed': self.closed, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'start': self.start, 'stop': self.stop, 'interval': self.interval, 'trades': self.trades, 'open': as_type(self.open), 'close': as_type(self.close), 'high': as_type(self.high), 'low': as_type(self.low), 'volume': as_type(self.volume), 'closed': self.closed, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} start: {self.start} stop: {self.stop} interval: {self.interval} trades: {self.trades} open: {self.open} close: {self.close} high: {self.high} low: {self.low} volume: {self.volume} closed: {self.closed} timestamp: {self.timestamp}"

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.start == cmp.start and self.stop == cmp.stop and self.interval == cmp.interval and self.trades == cmp.trades and self.open == cmp.open and self.close == cmp.close and self.high == cmp.high and self.low == cmp.low and self.volume == cmp.volume and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Index:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, price, timestamp, raw=None):
        assert isinstance(price, Decimal)

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

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.price == cmp.price and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class OpenInterest:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object open_interest
    cdef readonly object timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, open_interest, timestamp, raw=None):
        assert isinstance(open_interest, Decimal)
        assert timestamp is None or isinstance(timestamp, float)

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

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.open_interest == cmp.open_interest and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


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

    def _delta(self, as_type) -> dict:
        return {
            BID: [tuple([as_type(v) if isinstance(v, Decimal) else v for v in value]) for value in self.delta[BID]],
            ASK: [tuple([as_type(v) if isinstance(v, Decimal) else v for v in value]) for value in self.delta[ASK]]
        }

    def to_dict(self, delta=False, as_type=None) -> dict:
        assert self.sequence_number is None or isinstance(self.sequence_number, int)
        assert self.checksum is None or isinstance(self.checksum, (str, int))
        assert self.timestamp is None or isinstance(self.timestamp, Decimal)

        def helper(x):
            if isinstance(x, dict):
                return {k: as_type(v) for k, v in x.items()}
            else:
                return as_type(x)

        if delta:
            if as_type is None:
                return {'exchange': self.exchange, 'symbol': self.symbol, 'delta': self.delta, 'timestamp': self.timestamp}
            return {'exchange': self.exchange, 'symbol': self.symbol, 'delta': self._delta(as_type) if self.delta else None, 'timestamp': self.timestamp}

        if as_type is None:
            book_dict = self.book.to_dict()
            return {'exchange': self.exchange, 'symbol': self.symbol, 'book': book_dict, 'delta': self.delta, 'timestamp': self.timestamp}

        book_dict = self.book.to_dict(to_type=helper)
        return {'exchange': self.exchange, 'symbol': self.symbol, 'book': book_dict, 'delta': self._delta(as_type)if self.delta else None, 'timestamp': self.timestamp}

    def __repr__(self):
        return f"exchange: {self.exchange} symbol: {self.symbol} book: {self.book} timestamp: {self.timestamp}"

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.delta == cmp.delta and self.timestamp == cmp.timestamp and self.sequence_number == cmp.sequence_number and self.checksum == cmp.checksum and self.book.to_dict() == cmp.book.to_dict()

    def __hash__(self):
        return hash(self.__repr__())


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
    cdef readonly object raw  # Can be dict or list

    def __init__(self, exchange, symbol, id, side, status, type, price, amount, remaining, timestamp, raw=None):
        assert isinstance(price, Decimal)
        assert isinstance(amount, Decimal)
        assert remaining is None or isinstance(remaining, Decimal)
        assert timestamp is None or isinstance(timestamp, float)

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

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'id': self.id, 'side': self.side, 'status': self.status, 'type': self.type, 'price': self.price, 'amount': self.amount, 'remaining': self.remaining, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'id': self.id, 'side': self.side, 'status': self.status, 'type': self.type, 'price': as_type(self.price), 'amount': as_type(self.amount), 'remaining': as_type(self.remaining), 'timestamp': self.timestamp}

    def __repr__(self):
        return f'exchange: {self.exchange} symbol: {self.symbol} id: {self.id} side: {self.side} status: {self.status} type: {self.type} price: {self.price} amount: {self.amount} remaining: {self.remaining} timestamp: {self.timestamp}'

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.id == cmp.id and self.status == cmp.status and self.type == cmp.type and self.price == cmp.price and self.amount == cmp.amount and self.remaining == cmp.remaining and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Balance:
    cdef readonly str exchange
    cdef readonly str currency
    cdef readonly object balance
    cdef readonly object reserved
    cdef readonly dict raw

    def __init__(self, exchange, currency, balance, reserved, raw=None):
        assert isinstance(balance, Decimal)
        assert reserved is None or isinstance(reserved, Decimal)

        self.exchange = exchange
        self.currency = currency
        self.balance = balance
        self.reserved = reserved
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'currency': self.currency, 'balance': self.balance, 'reserved': self.reserved}
        return {'exchange': self.exchange, 'currency': self.currency, 'balance': as_type(self.balance), 'reserved': as_type(self.reserved)}

    def __repr__(self):
        return f'exchange: {self.exchange} currency: {self.currency} balance: {self.balance} reserved: {self.reserved}'

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.currency == cmp.currency and self.balance == cmp.balance and self.reserved == cmp.reserved

    def __hash__(self):
        return hash(self.__repr__())


cdef class L1Book:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object bid_price
    cdef readonly object bid_size
    cdef readonly object ask_price
    cdef readonly object ask_size
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, symbol, bid_price, bid_size, ask_price, ask_size, timestamp, raw=None):
        assert isinstance(bid_price, Decimal)
        assert isinstance(bid_size, Decimal)
        assert isinstance(ask_price, Decimal)
        assert isinstance(ask_size, Decimal)

        self.exchange = exchange
        self.symbol = symbol
        self.bid_price = bid_price
        self.bid_size = bid_size
        self.ask_price = ask_price
        self.ask_size = ask_size
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'bid_price': self.bid_price, 'bid_size': self.bid_size, 'ask_price': self.ask_price, 'ask_size': self.ask_size, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'bid_price': as_type(self.bid_price), 'bid_size': as_type(self.bid_size), 'ask_price': as_type(self.ask_price), 'ask_size': as_type(self.ask_size), 'timestamp': self.timestamp}

    def __repr__(self):
        return f'exchange: {self.exchange} symbol: {self.symbol} bid_price: {self.bid_price} bid_size: {self.bid_size}, ask_price: {self.ask_price} ask_size: {self.ask_size} timestamp: {self.timestamp}'

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.bid_price == cmp.bid_price and self.bid_size == cmp.bid_size and self.ask_price == cmp.ask_price and self.ask_size == cmp.ask_size and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Transaction:
    cdef readonly str exchange
    cdef readonly str currency
    cdef readonly str type
    cdef readonly str status
    cdef readonly object amount
    cdef readonly double timestamp
    cdef readonly dict raw

    def __init__(self, exchange, currency, type, status, amount, timestamp, raw=None):
        assert isinstance(amount, Decimal)

        self.exchange = exchange
        self.currency = currency
        self.type = type
        self.status = status
        self.amount = amount
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'currency': self.currency, 'type': self.type, 'status': self.status, 'amount': self.amount, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'currency': self.currency, 'type': self.type, 'status': self.status, 'amount': as_type(self.amount), 'timestamp': self.timestamp}

    def __repr__(self):
        return f'exchange: {self.exchange} currency: {self.currency} type: {self.type} status: {self.status} amount: {self.amount} timestamp {self.timestamp}'

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.currency == cmp.currency and self.type == cmp.type and self.status == cmp.status and self.amount == cmp.amount and self.timestamp == cmp.timestamp

    def __hash__(self):
        return hash(self.__repr__())


cdef class Fill:
    cdef readonly str exchange
    cdef readonly str symbol
    cdef readonly object price
    cdef readonly object amount
    cdef readonly str side
    cdef readonly object fee
    cdef readonly str id
    cdef readonly str order_id
    cdef readonly str liquidity
    cdef readonly str type
    cdef readonly double timestamp
    cdef readonly object raw  # can be dict or list

    def __init__(self, exchange, symbol, side, amount, price, fee, id, order_id, type, liquidity, timestamp, raw=None):
        assert isinstance(price, Decimal)
        assert isinstance(amount, Decimal)
        assert fee is None or isinstance(fee, Decimal)

        self.exchange = exchange
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.price = price
        self.fee = fee
        self.id = id
        self.order_id = id
        self.type = type
        self.liquidity = liquidity
        self.timestamp = timestamp
        self.raw = raw

    cpdef dict to_dict(self, as_type=None):
        if as_type is None:
            return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': self.amount, 'price': self.price, 'fee': self.fee, 'liquidity': self.liquidity, 'id': self.id, 'order_id': self.order_id, 'type': self.type, 'timestamp': self.timestamp}
        return {'exchange': self.exchange, 'symbol': self.symbol, 'side': self.side, 'amount': as_type(self.amount), 'price': as_type(self.price), 'fee': as_type(self.fee), 'liquidity': self.liquidity, 'id': self.id, 'order_id': self.order_id, 'type': self.type, 'timestamp': self.timestamp}

    def __repr__(self):
        return f'exchange: {self.exchange} symbol: {self.symbol} side: {self.side} amount: {self.amount} price: {self.price} fee: {self.fee} liquidity: {self.liquidity} id: {self.id} order_id: {self.order_id} type: {self.type} timestamp: {self.timestamp}'

    def __eq__(self, cmp):
        return self.exchange == cmp.exchange and self.symbol == cmp.symbol and self.price == cmp.price and self.amount == cmp.amount and self.side == cmp.side and self.id == cmp.id and self.timestamp == cmp.timestamp and self.fee == cmp.fee and self.liquidity == cmp.liquidity and self.order_id == cmp.order_id and self.type == cmp.type

    def __hash__(self):
        return hash(self.__repr__())
