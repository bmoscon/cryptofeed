'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Defines contains all constant string definitions for Cryptofeed,
as well as some documentation (in comment form) regarding
the book definitions and structure
'''
BITFINEX = 'BITFINEX'
BITHUMB = 'BITHUMB'
BINANCE = 'BINANCE'
BINANCE_US = 'BINANCE_US'
BINANCE_FUTURES = 'BINANCE_FUTURES'
BINANCE_DELIVERY = 'BINANCE_DELIVERY'
BITFLYER = 'BITFLYER'
BITGET = 'BITGET'
BITSTAMP = 'BITSTAMP'
BYBIT = 'BYBIT'
COINBASE = 'COINBASE'
CRYPTODOTCOM = "CRYPTO.COM"
DERIBIT = 'DERIBIT'
GATEIO = 'GATEIO'
GATEIO_FUTURES = 'GATEIO_FUTURES'
GEMINI = 'GEMINI'
DYDX = 'DYDX'
HYPERLIQUID = 'HYPERLIQUID'
MEXC = 'MEXC'
HTX = 'HTX'
HTX_SWAP = 'HTX_SWAP'
INDEPENDENT_RESERVE = 'INDEPENDENT_RESERVE'
KRAKEN = 'KRAKEN'
KRAKEN_FUTURES = 'KRAKEN_FUTURES'
KUCOIN = 'KUCOIN'
KUCOIN_FUTURES = 'KUCOIN_FUTURES'
OKX = 'OKX'
PHEMEX = 'PHEMEX'
POLONIEX = 'POLONIEX'
UPBIT = 'UPBIT'


# Market Data
L1_BOOK = 'l1_book'
L2_BOOK = 'l2_book'
L3_BOOK = 'l3_book'
TRADES = 'trades'
TICKER = 'ticker'
FUNDING = 'funding'
OPEN_INTEREST = 'open_interest'
LIQUIDATIONS = 'liquidations'
INDEX = 'index'
CANDLES = 'candles'

BUY = 'buy'
SELL = 'sell'
BID = 'bid'
ASK = 'ask'

FILLED = 'filled'
UNFILLED = 'unfilled'

# Instrument Definitions

CURRENCY = 'currency'
FUTURES = 'futures'
PERPETUAL = 'perpetual'
OPTION = 'option'
OPTION_COMBO = 'option_combo'
FUTURE_COMBO = 'future_combo'
SPOT = 'spot'
CALL = 'call'
PUT = 'put'
FX = 'fx'


# HTTP methods
GET = 'GET'
DELETE = 'DELETE'
POST = 'POST'


"""
L2 Orderbook Layout
    * BID and ASK are SortedDictionaries
    * PRICE and SIZE are of type decimal.Decimal

{
    symbol: {
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
    symbol: {
        ...
    },
    ...
}


L3 Orderbook Layout
    * Similar to L2, except orders are not aggregated by price,
      each price level contains the individual orders for that price level
{
    Symbol: {
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
    Symbol: {
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
