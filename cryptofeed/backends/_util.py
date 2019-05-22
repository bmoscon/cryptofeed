'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BID, ASK


def book_delta_convert(delta: dict, data: dict):
    for side in (BID, ASK):
        for entry in delta[side]:
            if len(entry) == 2:
                # level 2 updates
                price, amount = entry
                data[side][str(price)] = str(amount)
            else:
                order_id, price, amount = entry
                price = str(price)
                if price in delta[side]:
                    delta[side][price][str(order_id)] = str(amount)
                else:
                    delta[side][price] = {str(order_id): str(amount)}


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
