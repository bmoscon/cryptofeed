'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
L2_BOOK = 'l2_book'
L3_BOOK = 'l3_book'
TRADES = 'trades'
TICKER = 'ticker'
VOLUME = 'volume'
UNSUPPORTED = 'unsupported'

BID = 'bid'
ASK = 'ask'

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
