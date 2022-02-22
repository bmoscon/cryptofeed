'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from time import time
import json

from cryptofeed.types import OrderInfo, OrderBook, Trade
from cryptofeed.defines import BUY, PENDING, LIMIT


def test_order_info():
    oi = OrderInfo(
            'COINBASE',
            'BTC-USD',
            None,
            BUY,
            PENDING,
            LIMIT,
            Decimal(40000.00),
            Decimal(1.25),
            Decimal(1.25),
            time()
        )
    d = oi.to_dict(numeric_type=str)
    d = json.dumps(d)
    d = json.loads(d)
    oi2 = OrderInfo.from_dict(d)
    assert oi == oi2


def test_order_book():
    ob = OrderBook(
        'COINBASE',
        'BTC-USD',
        bids={100: 1, 200: 2, 300: 3, 400: 4, 500: 5},
        asks={600: 6, 700: 7, 800: 8, 1000: 10}
    )
    ob.timestamp = time()
    d = ob.to_dict()
    ob2 = OrderBook.from_dict(d)
    assert ob.book.to_dict() == ob2.book.to_dict()
    assert ob == ob2


def test_trade():
    t = Trade(
        'COINBASE',
        'BTC-USD',
        BUY,
        Decimal(10),
        Decimal(100),
        time(),
        id=str(int(time())),
        type='TEST'
    )
    d = t.to_dict(numeric_type=str)
    d = json.dumps(d)
    d = json.loads(d)
    t2 = Trade.from_dict(d)
    assert t == t2
