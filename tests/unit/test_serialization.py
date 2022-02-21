'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from time import time
import json

from cryptofeed.types import OrderInfo
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
