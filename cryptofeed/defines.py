'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
L2_BOOK = 'l2_book'
L3_BOOK = 'l3_book'
BOOK_DELTA = 'book_delta'
TRADES = 'trades'
TICKER = 'ticker'
VOLUME = 'volume'
FUNDING = 'funding'
UNSUPPORTED = 'unsupported'

BID = 'bid'
ASK = 'ask'

ADD = 'add'
DEL = 'delete'
UPD = 'update'

"""
Orderbook Layout
    * BID and ASK are SortedDictionaries
    * Currency Pairs are defined in standards.py
    * PRICE and SIZE are of type decimal.Decimal

{
    currency pair: {
        BID: {
            PRICE: SIZE,
            PRICE: SIZE,
            ...
        },
        ASK: {
            PRICE: SIZE,
            PRICE: SIZE,
            ...
        }
    },
    currency pair: {
        ...
    },
    ...
}
"""

"""
    Delta is in format of:
    {
        BID: {
            ADD: [(price, size), (price, size), ...],
            DEL: [price, price, price, ...]
            UPD: [(price, size), (price, size), ...]
        },
        ASK: {
            ADD: [(price, size), (price, size), ...],
            DEL: [price, price, price, ...]
            UPD: [(price, size), (price, size), ...]
        }
    }

    ADD - these tuples should simply be inserted.
    DEL - price levels should be deleted
    UPD - prices should have the quantity set to size (these are not price deltas)
"""
