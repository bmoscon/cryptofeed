'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Defines contains all constant string definitions for Cryptofeed,
as well as some documentation (in comment form) regarding
the book definitions and structure
'''
BITFINEX = 'BITFINEX'
BITMEX = 'BITMEX'
BINANCE = 'BINANCE'
BINANCE_US = 'BINANCE_US'
BINANCE_JERSEY = 'BINANCE_JERSEY'
BINANCE_FUTURES = 'BINANCE_FUTURES'
BITSTAMP = 'BITSTAMP'
BITTREX = 'BITTREX'
BYBIT = 'BYBIT'
COINBASE = 'COINBASE'
COINBENE = 'COINBENE'
DERIBIT = 'DERIBIT'
EXX = 'EXX'
FTX = 'FTX'
GEMINI = 'GEMINI'
HITBTC = 'HITBTC'
HUOBI = 'HUOBI'
HUOBI_DM = 'HUOBI_DM'
KRAKEN = 'KRAKEN'
KRAKEN_FUTURES = 'KRAKEN_FUTURES'
OKCOIN = 'OKCOIN'
OKEX = 'OKEX'
POLONIEX = 'POLONIEX'
BITCOINCOM = 'BITCOINCOM'
BITMAX = 'BITMAX'


L2_BOOK = 'l2_book'
L3_BOOK = 'l3_book'
BOOK_DELTA = 'book_delta'
TRADES = 'trades'
TICKER = 'ticker'
VOLUME = 'volume'
FUNDING = 'funding'
OPEN_INTEREST = 'open_interest'
UNSUPPORTED = 'unsupported'


L2_BOOK_SWAP = 'l2_book_swap'
TRADES_SWAP = 'trades_swap'
TICKER_SWAP = 'ticker_swap'


L2_BOOK_FUTURES = 'l2_book_futures'
TRADES_FUTURES = 'trades_futures'
TICKER_FUTURES = 'ticker_futures'


BUY = 'buy'
SELL = 'sell'
BID = 'bid'
ASK = 'ask'
UND = 'undefined'


LIMIT = 'limit'
MARKET = 'market'
MAKER_OR_CANCEL = 'maker-or-cancel'
FILL_OR_KILL = 'fill-or-kill'
IMMEDIATE_OR_CANCEL = 'immediate-or-cancel'


OPEN = 'open'
PENDING = 'pending'
FILLED = 'filled'
PARTIAL = 'partial'
CANCELLED = 'cancelled'


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



Trading Responses

Balances:

{
    coin/fiat: {
        total: Decimal, # total amount
        available: Decimal # available for trading
    },
    ...
}


Orders:

[
    {
        order_id: str,
        symbol: str,
        side: str,
        order_type: limit/market/etc,
        price: Decimal,
        total: Decimal,
        executed: Decimal,
        pending: Decimal,
        timestamp: float,
        order_status: FILLED/PARTIAL/CANCELLED/OPEN
    },
    {...},
    ...

]


Trade history:
[{
    'price': Decimal,
    'amount': Decimal,
    'timestamp': float,
    'side': str
    'fee_currency': str,
    'fee_amount': Decimal,
    'trade_id': str,
    'order_id': str
    },
    {
        ...
    }
]

"""
