'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Contains all code to normalize and standardize the differences
between exchanges. These include trading symbols, timestamps, and
data channel names
'''
import logging
import datetime as dt

from cryptofeed.defines import (BEQUANT, BITCOINCOM, BITFLYER, BITFINEX,
                                BITHUMB, ASCENDEX, BITMEX, PHEMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, CANDLES, COINBASE,
                                DERIBIT, DYDX, EXX, GATEIO, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN_FUTURES, KUCOIN, OKCOIN, OKEX, PROBIT, UPBIT)
from cryptofeed.defines import (FILL_OR_KILL, IMMEDIATE_OR_CANCEL, LIMIT, MAKER_OR_CANCEL, MARKET, UNSUPPORTED)
from cryptofeed.defines import (BALANCES, TRANSACTIONS, FUNDING, FUTURES_INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST,
                                TICKER, TRADES, ORDER_INFO, L1_BOOK, USER_FILLS, USER_DATA, LAST_PRICE)
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedTradingOption


LOG = logging.getLogger('feedhandler')


_feed_to_exchange_map = {
    L1_BOOK: {
        DERIBIT: 'quote',
    },
    L2_BOOK: {
        DYDX: 'v3_orderbook',
        BEQUANT: 'subscribeOrderbook',
        BITFINEX: 'book-P0-F0-100',
        BITFLYER: 'lightning_board_{}',
        BITHUMB: 'orderbookdepth',
        HITBTC: 'subscribeOrderbook',
        COINBASE: 'level2',
        BITMEX: 'orderBookL2',
        BITSTAMP: 'diff_order_book',
        KRAKEN_FUTURES: 'book',
        BLOCKCHAIN: 'l2',
        EXX: 'ENTRUST_ADD',
        HUOBI: 'depth.step0',
        HUOBI_DM: 'depth.step0',
        HUOBI_SWAP: 'depth.step0',
        OKCOIN: 'spot/depth_l2_tbt',
        OKEX: 'books-l2-tbt',
        DERIBIT: 'book',
        BYBIT: 'orderBookL2_25',
        BITTREX: 'orderbook_{}_{}',
        BITCOINCOM: 'subscribeOrderbook',
        ASCENDEX: "depth:",
        UPBIT: L2_BOOK,
        GATEIO: 'spot.order_book_update',
        PROBIT: 'order_books',
        KUCOIN: '/market/level2',
        PHEMEX: 'orderbook.subscribe'
    },
    L3_BOOK: {
        BITFINEX: 'book-R0-F0-100',
        BITSTAMP: 'detail_order_book',
        COINBASE: 'full',
        BLOCKCHAIN: 'l3',
    },
    TRADES: {
        DYDX: 'v3_trades',
        BEQUANT: 'subscribeTrades',
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        BITFLYER: 'lightning_executions_{}',
        BITHUMB: 'transaction',
        COINBASE: 'matches',
        BITMEX: 'trade',
        KRAKEN_FUTURES: 'trade',
        BLOCKCHAIN: 'trades',
        EXX: 'TRADE',
        HUOBI: 'trade.detail',
        HUOBI_DM: 'trade.detail',
        HUOBI_SWAP: 'trade.detail',
        OKCOIN: 'spot/trade',
        OKEX: 'trades',
        DERIBIT: 'trades',
        BYBIT: 'trade',
        BITTREX: 'trade_{}',
        BITCOINCOM: 'subscribeTrades',
        ASCENDEX: "trades:",
        UPBIT: TRADES,
        GATEIO: 'spot.trades',
        PROBIT: 'recent_trades',
        KUCOIN: '/market/match',
        PHEMEX: 'trade.subscribe'
    },
    TICKER: {
        BEQUANT: 'subscribeTicker',
        HITBTC: 'subscribeTicker',
        BITFINEX: 'ticker',
        BITSTAMP: UNSUPPORTED,
        COINBASE: 'ticker',
        BITMEX: 'quote',
        BITFLYER: 'lightning_ticker_{}',
        KRAKEN_FUTURES: 'ticker_lite',
        OKCOIN: '{}/ticker',
        OKEX: 'tickers',
        DERIBIT: "ticker",
        BITTREX: 'ticker_{}',
        BITCOINCOM: 'subscribeTicker',
        ASCENDEX: UNSUPPORTED,
        UPBIT: UNSUPPORTED,
        GATEIO: 'spot.tickers',
        PROBIT: UNSUPPORTED,
        KUCOIN: '/market/ticker',
        BITHUMB: UNSUPPORTED
    },
    FUNDING: {
        BITMEX: 'funding',
        BITFINEX: 'trades',
        KRAKEN_FUTURES: 'ticker',
        DERIBIT: 'ticker',
        OKEX: 'funding-rate',
        HUOBI_SWAP: 'funding'
    },
    OPEN_INTEREST: {
        OKEX: '{}/ticker',
        BITMEX: 'instrument',
        KRAKEN_FUTURES: 'ticker',
        DERIBIT: 'ticker',
        BYBIT: 'instrument_info.100ms'
    },
    LIQUIDATIONS: {
        BITMEX: 'liquidation',
        
        DERIBIT: 'trades',
        OKEX: LIQUIDATIONS,
    },
    FUTURES_INDEX: {
        BYBIT: 'instrument_info.100ms'
    },
    ORDER_INFO: {
        OKEX: ORDER_INFO,
        BEQUANT: 'subscribeReports',
        BITCOINCOM: 'subscribeReports',
        HITBTC: 'subscribeReports',
        BYBIT: 'order',
        DERIBIT: 'user.orders',

    },
    USER_FILLS: {
        BYBIT: 'execution',
        DERIBIT: 'user.trades',
    },
    CANDLES: {
        BEQUANT: 'subscribeCandles',
        BITCOINCOM: 'subscribeCandles',
        HITBTC: 'subscribeCandles',
        HUOBI: 'kline',
        GATEIO: 'spot.candlesticks',
        KUCOIN: '/market/candles',
        BITTREX: 'candle_{}_{}',
        PHEMEX: 'kline.subscribe'
    },
    TRANSACTIONS: {
        BEQUANT: 'subscribeTransactions',
        BITCOINCOM: 'subscribeTransactions',
        HITBTC: 'subscribeTransactions',
    },
    BALANCES: {
        BEQUANT: 'subscribeBalance',
        BITCOINCOM: 'subscribeBalance',
        HITBTC: 'subscribeBalance',
        DERIBIT: 'user.portfolio',
    },
    USER_DATA: {
        DERIBIT: 'user.changes',
        PHEMEX: 'aop.subscribe',
    },
    LAST_PRICE: {
        PHEMEX: 'tick.subscribe',
    },
}

_exchange_options = {
    LIMIT: {
        BEQUANT: 'limit',
        BITCOINCOM: 'limit',
        HITBTC: 'limit',
        BLOCKCHAIN: 'limit',
    },
    MARKET: {
        BEQUANT: 'market',
        BITCOINCOM: 'market',
        HITBTC: 'market',
        BLOCKCHAIN: 'market',
    },
    FILL_OR_KILL: {
        BEQUANT: {'timeInForce': 'FOK'},
        BITCOINCOM: {'timeInForce': 'FOK'},
        HITBTC: {'timeInForce': 'FOK'},
        BLOCKCHAIN: 'FOK'
    },
    IMMEDIATE_OR_CANCEL: {
        BEQUANT: {'timeInForce': 'IOC'},
        BITCOINCOM: {'timeInForce': 'IOC'},
        HITBTC: {'timeInForce': 'IOC'},
        BLOCKCHAIN: 'IOC'
    },
    MAKER_OR_CANCEL: {
        BEQUANT: {'postOnly': 1},
        BITCOINCOM: {'postOnly': 1},
        HITBTC: {'postOnly': 1},
    }
}
