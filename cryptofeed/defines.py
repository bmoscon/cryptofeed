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

DEL = 'delete'
UPD = 'update'

"""
L2 Orderbook Layout
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


L3 Orderbook Layout
    * Similar to L2, except orders are not aggregated by price,
      each price level contains the individual orders for that price level
{
    currency pair: {
        BID: {
            PRICE: {
                order-id: amount,
                order-id: amount,
                order-id: amount
            },
            PRICE: {
                order-id: amount,
                order-id: amount,
                order-id: amount
            }
            ...
        },
        ASK: {
            PRICE: {
                order-id: amount,
                order-id: amount,
                order-id: amount
            },
            PRICE: {
                order-id: amount,
                order-id: amount,
                order-id: amount
            }
            ...
        }
    },
    currency pair: {
        ...
    },
    ...
}


Delta is in format of:

for L2 books, it is as below
for L3 books:
    * DEL will be an array of order-id, price tuples
    * UPD will include order-id in each tuple

    {
        BID: {
            DEL: [price, price, price, ...]
            UPD: [(price, size), (price, size), ...]
        },
        ASK: {
            DEL: [price, price, price, ...]
            UPD: [(price, size), (price, size), ...]
        }
    }

    DEL - price levels should be deleted (for L3 the order id should be deleted, if the price level is now empty, delete the price level)
    UPD - prices should have the quantity set to size (these are not price deltas). For L3, add the order id at the price level
"""
