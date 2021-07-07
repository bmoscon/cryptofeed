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

from cryptofeed.defines import (BEQUANT, BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BINANCE_US, BITCOINCOM, BITFLYER, BITFINEX,
                                BITHUMB, ASCENDEX, BITMEX, PHEMEX, BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, CANDLES, COINBASE, COINGECKO,
                                DERIBIT, DYDX, EXX, FTX, FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN, KRAKEN_FUTURES, KUCOIN, OKCOIN, OKEX, POLONIEX, PROBIT, ACC_TRANSACTIONS, UPBIT, USER_FILLS)
from cryptofeed.defines import (FILL_OR_KILL, IMMEDIATE_OR_CANCEL, LIMIT, MAKER_OR_CANCEL, MARKET, UNSUPPORTED)
from cryptofeed.defines import (ACC_BALANCES, FUNDING, FUTURES_INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, MARKET_INFO,
                                TICKER, TRADES, ORDER_INFO)
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedTradingOption


LOG = logging.getLogger('feedhandler')


def timestamp_normalize(exchange, ts):
    if exchange == BYBIT:
        if isinstance(ts, int):
            return ts / 1000
        else:
            return ts.timestamp()
        
    if exchange in {BITFLYER, COINBASE, BLOCKCHAIN, BITMEX, HITBTC, OKCOIN, FTX, FTX_US, BITCOINCOM, PROBIT, COINGECKO, BITTREX, DYDX, BEQUANT}:
        return ts.timestamp()
    elif exchange in {OKEX, HUOBI, HUOBI_DM, HUOBI_SWAP, BITFINEX, DERIBIT, BINANCE, BINANCE_US, BINANCE_FUTURES,
                      BINANCE_DELIVERY, GEMINI, ASCENDEX, KRAKEN_FUTURES, UPBIT}:

        return ts / 1000.0
    elif exchange in {BITSTAMP}:
        return ts / 1_000_000.0
    elif exchange == PHEMEX:
        return ts / 1_000_000_000.0
    elif exchange in {BITHUMB}:
        return (ts - dt.timedelta(hours=9)).timestamp()


_feed_to_exchange_map = {
    L2_BOOK: {
        DYDX: 'v3_orderbook',
        BEQUANT: 'subscribeOrderbook',
        BITFINEX: 'book-P0-F0-100',
        BITFLYER: 'lightning_board_{}',
        BITHUMB: 'orderbookdepth',
        POLONIEX: L2_BOOK,
        HITBTC: 'subscribeOrderbook',
        COINBASE: 'level2',
        BITMEX: 'orderBookL2',
        BITSTAMP: 'diff_order_book',
        KRAKEN: 'book',
        KRAKEN_FUTURES: 'book',
        BINANCE: 'depth@100ms',
        BINANCE_US: 'depth@100ms',
        BINANCE_FUTURES: 'depth@100ms',
        BINANCE_DELIVERY: 'depth@100ms',
        BLOCKCHAIN: 'l2',
        EXX: 'ENTRUST_ADD',
        HUOBI: 'depth.step0',
        HUOBI_DM: 'depth.step0',
        HUOBI_SWAP: 'depth.step0',
        OKCOIN: 'spot/depth_l2_tbt',
        OKEX: 'books-l2-tbt',
        DERIBIT: 'book',
        BYBIT: 'orderBookL2_25',
        FTX: 'orderbook',
        FTX_US: 'orderbook',
        GEMINI: L2_BOOK,
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
        BEQUANT: UNSUPPORTED,
        BITTREX: UNSUPPORTED,
        BITFINEX: 'book-R0-F0-100',
        BITHUMB: UNSUPPORTED,
        BITSTAMP: 'detail_order_book',
        HITBTC: UNSUPPORTED,
        COINBASE: 'full',
        BITMEX: UNSUPPORTED,
        POLONIEX: UNSUPPORTED,  # supported by specifying a trading symbol as the channel,
        KRAKEN: UNSUPPORTED,
        KRAKEN_FUTURES: UNSUPPORTED,
        BINANCE: UNSUPPORTED,
        BINANCE_US: UNSUPPORTED,
        BINANCE_FUTURES: UNSUPPORTED,
        BINANCE_DELIVERY: UNSUPPORTED,
        BLOCKCHAIN: 'l3',
        EXX: UNSUPPORTED,
        HUOBI: UNSUPPORTED,
        HUOBI_DM: UNSUPPORTED,
        OKCOIN: UNSUPPORTED,
        OKEX: UNSUPPORTED,
        BYBIT: UNSUPPORTED,
        FTX: UNSUPPORTED,
        FTX_US: UNSUPPORTED,
        GEMINI: UNSUPPORTED,
        BITCOINCOM: UNSUPPORTED,
        ASCENDEX: UNSUPPORTED,
        UPBIT: UNSUPPORTED,
        PROBIT: UNSUPPORTED
    },
    TRADES: {
        DYDX: 'v3_trades',
        BEQUANT: 'subscribeTrades',
        POLONIEX: TRADES,
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        BITFLYER: 'lightning_executions_{}',
        BITHUMB: 'transaction',
        COINBASE: 'matches',
        BITMEX: 'trade',
        KRAKEN: 'trade',
        KRAKEN_FUTURES: 'trade',
        BINANCE: 'aggTrade',
        BINANCE_US: 'aggTrade',
        BINANCE_FUTURES: 'aggTrade',
        BINANCE_DELIVERY: 'aggTrade',
        BLOCKCHAIN: 'trades',
        EXX: 'TRADE',
        HUOBI: 'trade.detail',
        HUOBI_DM: 'trade.detail',
        HUOBI_SWAP: 'trade.detail',
        OKCOIN: 'spot/trade',
        OKEX: 'trades',
        DERIBIT: 'trades',
        BYBIT: 'trade',
        FTX: 'trades',
        FTX_US: 'trades',
        GEMINI: TRADES,
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
        POLONIEX: 1002,
        HITBTC: 'subscribeTicker',
        BITFINEX: 'ticker',
        BITSTAMP: UNSUPPORTED,
        COINBASE: 'ticker',
        BITMEX: 'quote',
        BITFLYER: 'lightning_ticker_{}',
        KRAKEN: TICKER,
        KRAKEN_FUTURES: 'ticker_lite',
        BINANCE: 'bookTicker',
        BINANCE_US: 'bookTicker',
        BINANCE_FUTURES: 'bookTicker',
        BINANCE_DELIVERY: 'bookTicker',
        BLOCKCHAIN: UNSUPPORTED,
        HUOBI: UNSUPPORTED,
        HUOBI_DM: UNSUPPORTED,
        OKCOIN: '{}/ticker',
        OKEX: 'tickers',
        DERIBIT: "ticker",
        BYBIT: UNSUPPORTED,
        FTX: "ticker",
        FTX_US: "ticker",
        GEMINI: UNSUPPORTED,
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
        BINANCE_FUTURES: 'markPrice',
        BINANCE_DELIVERY: 'markPrice',
        KRAKEN_FUTURES: 'ticker',
        DERIBIT: 'ticker',
        OKEX: 'funding-rate',
        FTX: 'funding',
        HUOBI_SWAP: 'funding'
    },
    OPEN_INTEREST: {
        OKEX: '{}/ticker',
        BITMEX: 'instrument',
        KRAKEN_FUTURES: 'ticker',
        DERIBIT: 'ticker',
        FTX: 'open_interest',
        BINANCE_FUTURES: 'open_interest',
        BINANCE_DELIVERY: 'open_interest',
        BYBIT: 'instrument_info.100ms'
    },
    LIQUIDATIONS: {
        BITMEX: 'liquidation',
        BINANCE_FUTURES: 'forceOrder',
        BINANCE_DELIVERY: 'forceOrder',
        FTX: 'trades',
        DERIBIT: 'trades',
        OKEX: LIQUIDATIONS,
    },
    MARKET_INFO: {
        COINGECKO: MARKET_INFO
    },
    FUTURES_INDEX: {
        BYBIT: 'instrument_info.100ms'
    },
    ORDER_INFO: {
        GEMINI: ORDER_INFO,
        OKEX: ORDER_INFO,
        FTX: 'orders',
        BEQUANT: 'subscribeReports',
        BITCOINCOM: 'subscribeReports',
        HITBTC: 'subscribeReports',
    },
    USER_FILLS: {
        FTX: 'fills',
    },
    CANDLES: {
        BEQUANT: 'subscribeCandles',
        BINANCE: 'kline_',
        BINANCE_US: 'kline_',
        BINANCE_FUTURES: 'kline_',
        BINANCE_DELIVERY: 'kline_',
        BITCOINCOM: 'subscribeCandles',
        HITBTC: 'subscribeCandles',
        HUOBI: 'kline',
        GATEIO: 'spot.candlesticks',
        KUCOIN: '/market/candles',
        KRAKEN: 'ohlc',
        BITTREX: 'candle_{}_{}',
        PHEMEX: 'kline.subscribe'
    },
    ACC_TRANSACTIONS: {
        BEQUANT: 'subscribeTransactions',
        BITCOINCOM: 'subscribeTransactions',
        HITBTC: 'subscribeTransactions',
    },
    ACC_BALANCES: {
        BEQUANT: 'subscribeBalance',
        BITCOINCOM: 'subscribeBalance',
        HITBTC: 'subscribeBalance',
    },
}

_exchange_options = {
    LIMIT: {
        BEQUANT: 'limit',
        BITCOINCOM: 'limit',
        HITBTC: 'limit',
        KRAKEN: 'limit',
        GEMINI: 'exchange limit',
        POLONIEX: 'limit',
        COINBASE: 'limit',
        BLOCKCHAIN: 'limit',
    },
    MARKET: {
        BEQUANT: 'market',
        BITCOINCOM: 'market',
        HITBTC: 'market',
        KRAKEN: 'market',
        GEMINI: UNSUPPORTED,
        POLONIEX: UNSUPPORTED,
        COINBASE: 'market',
        BLOCKCHAIN: 'market',
    },
    FILL_OR_KILL: {
        BEQUANT: {'timeInForce': 'FOK'},
        BITCOINCOM: {'timeInForce': 'FOK'},
        HITBTC: {'timeInForce': 'FOK'},
        GEMINI: 'fill-or-kill',
        POLONIEX: 'fillOrKill',
        COINBASE: {'time_in_force': 'FOK'},
        KRAKEN: UNSUPPORTED,
        BLOCKCHAIN: 'FOK'
    },
    IMMEDIATE_OR_CANCEL: {
        BEQUANT: {'timeInForce': 'IOC'},
        BITCOINCOM: {'timeInForce': 'IOC'},
        GEMINI: 'immediate-or-cancel',
        HITBTC: {'timeInForce': 'IOC'},
        POLONIEX: 'immediateOrCancel',
        COINBASE: {'time_in_force': 'IOC'},
        KRAKEN: UNSUPPORTED,
        BLOCKCHAIN: 'IOC'
    },
    MAKER_OR_CANCEL: {
        BEQUANT: {'postOnly': 1},
        BITCOINCOM: {'postOnly': 1},
        GEMINI: 'maker-or-cancel',
        HITBTC: {'postOnly': 1},
        POLONIEX: 'postOnly',
        COINBASE: {'post_only': 1},
        KRAKEN: 'post'
    }
}


def normalize_trading_options(exchange, option):
    if option not in _exchange_options:
        raise UnsupportedTradingOption
    if exchange not in _exchange_options[option]:
        raise UnsupportedTradingOption

    ret = _exchange_options[option][exchange]
    if ret == UNSUPPORTED:
        raise UnsupportedTradingOption
    return ret


def feed_to_exchange(exchange, feed, silent=False):
    def raise_error():
        exception = UnsupportedDataFeed(f"{feed} is not currently supported on {exchange}")
        if not silent:
            LOG.error("Error: %r", exception)
        raise exception

    try:
        ret = _feed_to_exchange_map[feed][exchange]
    except KeyError:
        raise_error()

    if ret == UNSUPPORTED:
        raise_error()
    return ret


def normalize_channel(exchange: str, feed: str) -> str:
    for chan, entries in _feed_to_exchange_map.items():
        if exchange in entries:
            if entries[exchange] == feed:
                return chan
    raise ValueError('Unable to normalize channel %s', feed)


def is_authenticated_channel(channel: str) -> bool:
    return channel in (ORDER_INFO, USER_FILLS, ACC_TRANSACTIONS, ACC_BALANCES)
