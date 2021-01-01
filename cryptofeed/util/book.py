'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


A set of helper functions for regulating book depth
'''
from sortedcontainers import SortedDict as sd

from cryptofeed.defines import BID, ASK, L2_BOOK


def depth(book: dict, depth: int, book_type=L2_BOOK) -> dict:
    """
    Take a book and return a new dict with max `depth` levels per side
    """
    ret = {BID: sd(), ASK: sd()}
    for side in (BID, ASK):
        prices = list(book[side].keys())[:depth] if side == ASK else list(book[side].keys())[-depth:]
        if book_type == L2_BOOK:
            for price in prices:
                ret[side][price] = book[side][price]
        else:
            for price in prices:
                ret[side][price] = {order_id: size for order_id, size in ret[side][price].items()}

    return ret


def book_delta(former: dict, latter: dict, book_type=L2_BOOK) -> list:
    ret = {BID: [], ASK: []}
    if book_type == L2_BOOK:
        for side in (BID, ASK):
            fkeys = set(list(former[side].keys()))
            lkeys = set(list(latter[side].keys()))
            for price in fkeys - lkeys:
                ret[side].append((price, 0))

            for price in lkeys - fkeys:
                ret[side].append((price, latter[side][price]))

            for price in lkeys.intersection(fkeys):
                if former[side][price] != latter[side][price]:
                    ret[side].append((price, latter[side][price]))
    else:
        raise ValueError("Not supported for L3 Books")

    return ret
