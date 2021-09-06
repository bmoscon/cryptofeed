'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Defines contains all constant string definitions for Cryptofeed,
as well as some documentation (in comment form) regarding
the book definitions and structure
'''
ASCENDEX = 'ASCENDEX'
BEQUANT = 'BEQUANT'
BITFINEX = 'BITFINEX'
BITHUMB = 'BITHUMB'
BITMEX = 'BITMEX'
BINANCE = 'BINANCE'
BINANCE_US = 'BINANCE_US'
BINANCE_FUTURES = 'BINANCE_FUTURES'
BINANCE_DELIVERY = 'BINANCE_DELIVERY'
BITFLYER = 'BITFLYER'
BITSTAMP = 'BITSTAMP'
BITTREX = 'BITTREX'
BLOCKCHAIN = 'BLOCKCHAIN'
BYBIT = 'BYBIT'
COINBASE = 'COINBASE'
DERIBIT = 'DERIBIT'
DYDX = 'DYDX'
EXX = 'EXX'
FTX = 'FTX'
FTX_US = 'FTX_US'
GATEIO = 'GATEIO'
GEMINI = 'GEMINI'
HITBTC = 'HITBTC'
HUOBI = 'HUOBI'
HUOBI_DM = 'HUOBI_DM'
HUOBI_SWAP = 'HUOBI_SWAP'
KRAKEN = 'KRAKEN'
KRAKEN_FUTURES = 'KRAKEN_FUTURES'
KUCOIN = 'KUCOIN'
OKCOIN = 'OKCOIN'
OKEX = 'OKEX'
PHEMEX = 'PHEMEX'
POLONIEX = 'POLONIEX'
PROBIT = 'PROBIT'
BITCOINCOM = 'BITCOINCOM'
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
UNSUPPORTED = 'unsupported'
CANDLES = 'candles'

# Account Data / Authenticated Channels
ORDER_INFO = 'order_info'
FILLS = 'fills'
TRANSACTIONS = 'transactions'
BALANCES = 'balances'
PLACE_ORDER = 'place_order'
CANCEL_ORDER = 'cancel_order'
ORDERS = 'orders'
ORDER_STATUS = 'order_status'
TRADE_HISTORY = 'trade_history'
POSITIONS = 'positions'

BUY = 'buy'
SELL = 'sell'
BID = 'bid'
ASK = 'ask'
UND = 'undefined'
MAKER = 'maker'
TAKER = 'taker'

LIMIT = 'limit'
MARKET = 'market'
STOP_LIMIT = 'stop-limit'
STOP_MARKET = 'stop-market'
MAKER_OR_CANCEL = 'maker-or-cancel'
FILL_OR_KILL = 'fill-or-kill'
IMMEDIATE_OR_CANCEL = 'immediate-or-cancel'
GOOD_TIL_CANCELED = 'good-til-canceled'

OPEN = 'open'
PENDING = 'pending'
FILLED = 'filled'
PARTIAL = 'partial'
CANCELLED = 'cancelled'
UNFILLED = 'unfilled'
EXPIRED = 'expired'
SUSPENDED = 'suspended'
FAILED = 'failed'
SUBMITTING = 'submitting'
CANCELLING = 'cancelling'
CLOSED = 'closed'

# Instrument Definitions

CURRENCY = 'currency'
FUTURES = 'futures'
PERPETUAL = 'perpetual'
OPTION = 'option'
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
