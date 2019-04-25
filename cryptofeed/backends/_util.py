'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BID, ASK


def book_convert(book: dict, data: dict, depth: int):
    """
    Build depth levels of book into data, converting decimal.Decimal
    to str. Book will remain unmodified, data will be modified
    """
    count = 0
    for level in book[ASK]:
        str_level = str(level)
        if isinstance(book[ASK][level], dict):
            data[ASK][str_level] = book[ASK][level]
            for order in data[ASK][str_level]:
                data[ASK][str_level][order] = str(data[ASK][str_level][order])
        else:
            data[ASK][str_level] = str(book[ASK][level])
        count += 1
        if depth and count >= depth:
            break

    count = 0
    for level in reversed(book[BID]):
        str_level = str(level)
        if isinstance(book[BID][level], dict):
            data[BID][str_level] = book[BID][level]
            for order in data[BID][str(level)]:
                data[BID][str_level][order] = str(data[BID][str_level][order])
        else:
            data[BID][str_level] = str(book[BID][level])
        count += 1
        if depth and count >= depth:
            break


def book_flatten(book: dict, timestamp: float) -> dict:
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
                    ret.append({'side': side, 'price': price, 'size': size, 'order_id': order_id, 'timestamp': timestamp})
            else:
                ret.append({'side': side, 'price': price, 'size': data, 'timestamp': timestamp})
    return ret
