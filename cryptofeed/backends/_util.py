'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from typing import Any, Dict, List, Union

from cryptofeed.defines import BID, ASK


def book_delta_convert(delta: dict, data: dict, convert=str):
    for side in (BID, ASK):
        for entry in delta[side]:
            if len(entry) == 2:
                # level 2 updates
                price, amount = entry
                data[side][convert(price)] = convert(amount)
            else:
                order_id, price, amount = entry
                price = convert(price)
                if price in data[side]:
                    data[side][price][order_id] = convert(amount)
                else:
                    data[side][price] = {order_id: convert(amount)}


def book_convert(book: dict, data: dict, convert=str):
    """
    Converting decimal.Decimal to str. Book will remain unmodified,
    data will be modified
    """
    for level in book[ASK]:
        _level = convert(level)
        if isinstance(book[ASK][level], dict):
            data[ASK][_level] = book[ASK][level]
            for order in data[ASK][_level]:
                data[ASK][_level][order] = convert(data[ASK][_level][order])
        else:
            data[ASK][_level] = convert(book[ASK][level])

    for level in reversed(book[BID]):
        _level = convert(level)
        if isinstance(book[BID][level], dict):
            data[BID][_level] = book[BID][level]
            for order in data[BID][convert(level)]:
                data[BID][_level][order] = convert(data[BID][_level][order])
        else:
            data[BID][_level] = convert(book[BID][level])


def book_flatten(feed: str, symbol: str, book: dict, timestamp: float, delta: str) -> List[Dict[str, Union[Union[str, float], Any]]]:
    """
    takes book and returns a list of dict, where each element in the list
    is a dictionary with a single row of book data.

    eg.
    L2:
    [{'side': str, 'price': float, 'size': float, 'timestamp': float}, {...}, ...]

    L3:
    [{'side': str, 'price': float, 'size': float, 'timestamp': float, 'order_id': str}, {...}, ...]
    """
    ret = []
    for side in (BID, ASK):
        for price, data in book[side].items():
            if isinstance(data, dict):
                # L3 book
                for order_id, size in data.items():
                    ret.append({'feed': feed, 'symbol': symbol, 'side': side, 'price': price, 'size': size, 'order_id': order_id, 'timestamp': timestamp, 'delta': delta})
            else:
                ret.append({'feed': feed, 'symbol': symbol, 'side': side, 'price': price, 'size': data, 'timestamp': timestamp, 'delta': delta})
    return ret
