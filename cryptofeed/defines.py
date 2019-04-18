'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Defines contains all constant string definitions for Cryptofeed,
as well as some documentation (in comment form) regarding
the book definitions and structure
'''
BITSTAMP = 'BITSTAMP'
BITFINEX = 'BITFINEX'
COINBASE = 'COINBASE'
GEMINI = 'GEMINI'
HITBTC = 'HITBTC'
POLONIEX = 'POLONIEX'
BITMEX = 'BITMEX'
KRAKEN = 'KRAKEN'
BINANCE = 'BINANCE'
EXX = 'EXX'
HUOBI = 'HUOBI'
HUOBI_US = 'HUOBI_US'
OKCOIN = 'OKCOIN'
OKEX = 'OKEX'
COINBENE = 'COINBENE'


L2_BOOK = 'l2_book'
L3_BOOK = 'l3_book'
BOOK_DELTA = 'book_delta'
TRADES = 'trades'
TICKER = 'ticker'
VOLUME = 'volume'
FUNDING = 'funding'
UNSUPPORTED = 'unsupported'

L2_BOOK_SWAP = 'l2_book_swap'
TRADES_SWAP = 'trades_swap'
TICKER_SWAP = 'ticker_swap'

BUY = 'buy'
SELL = 'sell'

BID = 'bid'
ASK = 'ask'
UND = 'undefined'

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
    * tuples will be order-id, price, size

    {
        BID: [ (price, size), (price, size), (price, size), ...],
        ASK: [ (price, size), (price, size), (price, size), ...]
    }

    For L2 books a size of 0 means the price level should be deleted.
    For L3 books, a size of 0 means the order should be deleted. If there are
    no orders at the price, the price level can be deleted.
"""
