'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import BID, ASK, L2_BOOK


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
