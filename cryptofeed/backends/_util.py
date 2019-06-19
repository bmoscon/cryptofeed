'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
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
                    data[side][price][convert(order_id)] = convert(amount)
                else:
                    data[side][price] = {convert(order_id): convert(amount)}


def book_convert(book: dict, data: dict, depth: int, convert=str):
    """
    Build depth levels of book into data, converting decimal.Decimal
    to str. Book will remain unmodified, data will be modified
    """
    count = 0
    for level in book[ASK]:
        _level = convert(level)
        if isinstance(book[ASK][level], dict):
            data[ASK][_level] = book[ASK][level]
            for order in data[ASK][_level]:
                data[ASK][_level][order] = convert(data[ASK][_level][order])
        else:
            data[ASK][_level] = convert(book[ASK][level])
        count += 1
        if depth and count >= depth:
            break

    count = 0
    for level in reversed(book[BID]):
        _level = convert(level)
        if isinstance(book[BID][level], dict):
            data[BID][_level] = book[BID][level]
            for order in data[BID][convert(level)]:
                data[BID][_level][order] = convert(data[BID][_level][order])
        else:
            data[BID][_level] = convert(book[BID][level])
        count += 1
        if depth and count >= depth:
            break
