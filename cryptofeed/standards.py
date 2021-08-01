'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Contains all code to normalize and standardize the differences
between exchanges. These include trading symbols, timestamps, and
data channel names
'''

from cryptofeed.defines import (
                                BITSTAMP, BITTREX, BLOCKCHAIN,
                                EXX, GATEIO, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN_FUTURES, KUCOIN, OKCOIN, OKEX, PROBIT, UPBIT)
from cryptofeed.defines import (FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST,
                                TICKER, TRADES, ORDER_INFO)



_feed_to_exchange_map = {
    L2_BOOK: {
        BITSTAMP: 'diff_order_book',
        KRAKEN_FUTURES: 'book',
        BLOCKCHAIN: 'l2',
        EXX: 'ENTRUST_ADD',
        HUOBI: 'depth.step0',
        HUOBI_DM: 'depth.step0',
        HUOBI_SWAP: 'depth.step0',
        OKCOIN: 'spot/depth_l2_tbt',
        OKEX: 'books-l2-tbt',
        BITTREX: 'orderbook_{}_{}',
        UPBIT: L2_BOOK,
        GATEIO: 'spot.order_book_update',
        PROBIT: 'order_books',
        KUCOIN: '/market/level2',
    },
    TRADES: {
        BITSTAMP: 'live_trades',
        KRAKEN_FUTURES: 'trade',
        BLOCKCHAIN: 'trades',
        EXX: 'TRADE',
        HUOBI: 'trade.detail',
        HUOBI_DM: 'trade.detail',
        HUOBI_SWAP: 'trade.detail',
        OKCOIN: 'spot/trade',
        OKEX: 'trades',
        BITTREX: 'trade_{}',
        UPBIT: TRADES,
        GATEIO: 'spot.trades',
        PROBIT: 'recent_trades',
        KUCOIN: '/market/match',
    },
    TICKER: {
        KRAKEN_FUTURES: 'ticker_lite',
        OKCOIN: '{}/ticker',
        OKEX: 'tickers',
        BITTREX: 'ticker_{}',
        GATEIO: 'spot.tickers',
        KUCOIN: '/market/ticker',
    },
    FUNDING: {
        KRAKEN_FUTURES: 'ticker',
        OKEX: 'funding-rate',
        HUOBI_SWAP: 'funding'
    },
    OPEN_INTEREST: {
        OKEX: '{}/ticker',
        KRAKEN_FUTURES: 'ticker',
    },
    LIQUIDATIONS: {
        OKEX: LIQUIDATIONS,
    },
    ORDER_INFO: {
        OKEX: ORDER_INFO,

    },
    
}