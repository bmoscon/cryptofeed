'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


Contains all code to normalize and standardize the differences
between exchanges. These include trading symbols, timestamps, and
data channel names
'''
import collections
import logging

import pandas as pd

from cryptofeed.defines import (BINANCE, BINANCE_DELIVERY, BINANCE_FUTURES, BINANCE_US, BITCOINCOM, BITFLYER, BITFINEX, BITMAX, BITMEX,
                                BITSTAMP, BITTREX, BLOCKCHAIN, BYBIT, CANDLES, COINBASE, COINGECKO,
                                DERIBIT, EXX, FTX, FTX_US, GATEIO, GEMINI, HITBTC, HUOBI, HUOBI_DM, HUOBI_SWAP,
                                KRAKEN, KRAKEN_FUTURES, OKCOIN, OKEX, POLONIEX, PROBIT, UPBIT, WHALE_ALERT)
from cryptofeed.defines import (FILL_OR_KILL, IMMEDIATE_OR_CANCEL, LIMIT, MAKER_OR_CANCEL, MARKET, UNSUPPORTED)
from cryptofeed.defines import (FUNDING, FUTURES_INDEX, L2_BOOK, L3_BOOK, LIQUIDATIONS, OPEN_INTEREST, MARKET_INFO,
                                TICKER, TRADES, TRANSACTIONS, VOLUME, ORDER_INFO)
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedTradingOption, UnsupportedSymbol
from cryptofeed.symbols import gen_symbols, _exchange_info

LOG = logging.getLogger('feedhandler')

_std_trading_symbols = collections.defaultdict(dict)
_exchange_to_std = {}


def load_exchange_symbol_mapping(exchange: str, key_id=None):
    mapping = gen_symbols(exchange, key_id=key_id)
    for std, exch in mapping.items():
        _exchange_to_std[exch] = std
        _std_trading_symbols[std][exchange] = exch


def get_exchange_info(exchange: str, key_id=None):
    mapping = gen_symbols(exchange, key_id=key_id)
    info = dict(_exchange_info.get(exchange, {}))
    return mapping, info


def symbol_std_to_exchange(symbol: str, exchange: str):
    if symbol in _std_trading_symbols:
        try:
            return _std_trading_symbols[symbol][exchange]
        except KeyError:
            raise UnsupportedSymbol(f'{symbol} is not supported on {exchange}')
    else:
        # Bitfinex supports funding symbols that are single currencies, prefixed with f
        if exchange == BITFINEX and '-' not in symbol:
            return f"f{symbol}"
        raise UnsupportedSymbol(f'{symbol} is not supported on {exchange}')


def symbol_exchange_to_std(symbol):
    if symbol in _exchange_to_std:
        return _exchange_to_std[symbol]
    # Bitfinex funding currency
    if symbol[0] == 'f':
        return symbol[1:]
    return None


def timestamp_normalize(exchange, ts):
    if exchange == BYBIT:
        if isinstance(ts, int):
            return ts / 1000
        else:
            return ts.timestamp()
    if exchange in {BITFLYER, COINBASE, BLOCKCHAIN}:
        return ts.timestamp()
    elif exchange in {BITMEX, HITBTC, OKCOIN, OKEX, FTX, FTX_US, BITCOINCOM, PROBIT, COINGECKO}:
        return pd.Timestamp(ts).timestamp()
    elif exchange in {HUOBI, HUOBI_DM, HUOBI_SWAP, BITFINEX, DERIBIT, BINANCE, BINANCE_US, BINANCE_FUTURES,
                      BINANCE_DELIVERY, GEMINI, BITTREX, BITMAX, KRAKEN_FUTURES, UPBIT}:
        return ts / 1000.0
    elif exchange in {BITSTAMP}:
        return ts / 1000000.0
    # WHALE_ALERT
    return ts


_feed_to_exchange_map = {
    L2_BOOK: {
        BITFINEX: 'book-P0-F0-100',
        BITFLYER: 'lightning_board_{}',
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
        OKEX: '{}/depth_l2_tbt',
        DERIBIT: 'book',
        BYBIT: 'orderBookL2_25',
        FTX: 'orderbook',
        FTX_US: 'orderbook',
        GEMINI: L2_BOOK,
        BITTREX: 'SubscribeToExchangeDeltas',
        BITCOINCOM: 'subscribeOrderbook',
        BITMAX: "depth:",
        UPBIT: L2_BOOK,
        GATEIO: 'depth.subscribe',
        PROBIT: 'order_books'
    },
    L3_BOOK: {
        BITFINEX: 'book-R0-F0-100',
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
        BITMAX: UNSUPPORTED,
        UPBIT: UNSUPPORTED,
        PROBIT: UNSUPPORTED
    },
    TRADES: {
        POLONIEX: TRADES,
        HITBTC: 'subscribeTrades',
        BITSTAMP: 'live_trades',
        BITFINEX: 'trades',
        BITFLYER: 'lightning_executions_{}',
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
        OKEX: '{}/trade',
        DERIBIT: 'trades',
        BYBIT: 'trade',
        FTX: 'trades',
        FTX_US: 'trades',
        GEMINI: TRADES,
        BITTREX: TRADES,
        BITCOINCOM: 'subscribeTrades',
        BITMAX: "trades:",
        UPBIT: TRADES,
        GATEIO: 'trades.subscribe',
        PROBIT: 'recent_trades'
    },
    TICKER: {
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
        OKEX: '{}/ticker',
        DERIBIT: "ticker",
        BYBIT: UNSUPPORTED,
        FTX: "ticker",
        FTX_US: "ticker",
        GEMINI: UNSUPPORTED,
        BITTREX: 'SubscribeToSummaryDeltas',
        BITCOINCOM: 'subscribeTicker',
        BITMAX: UNSUPPORTED,
        UPBIT: UNSUPPORTED,
        GATEIO: UNSUPPORTED,
        PROBIT: UNSUPPORTED
    },
    VOLUME: {
        POLONIEX: 1003
    },
    FUNDING: {
        BITMEX: 'funding',
        BITFINEX: 'trades',
        BINANCE_FUTURES: 'markPrice',
        BINANCE_DELIVERY: 'markPrice',
        KRAKEN_FUTURES: 'ticker',
        DERIBIT: 'ticker',
        OKEX: '{}/funding_rate',
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
    TRANSACTIONS: {
        WHALE_ALERT: TRANSACTIONS
    },
    FUTURES_INDEX: {
        BYBIT: 'instrument_info.100ms'
    },
    ORDER_INFO: {
        GEMINI: ORDER_INFO,
        OKEX: ORDER_INFO
    },
    CANDLES: {
        BINANCE: 'kline_',
        BINANCE_FUTURES: 'kline_',
    }
}

_exchange_options = {
    LIMIT: {
        KRAKEN: 'limit',
        GEMINI: 'exchange limit',
        POLONIEX: 'limit',
        COINBASE: 'limit',
        BLOCKCHAIN: 'limit',
    },
    MARKET: {
        KRAKEN: 'market',
        GEMINI: UNSUPPORTED,
        POLONIEX: UNSUPPORTED,
        COINBASE: 'market',
        BLOCKCHAIN: 'market',
    },
    FILL_OR_KILL: {
        GEMINI: 'fill-or-kill',
        POLONIEX: 'fillOrKill',
        COINBASE: {'time_in_force': 'FOK'},
        KRAKEN: UNSUPPORTED,
        BLOCKCHAIN: 'FOK'
    },
    IMMEDIATE_OR_CANCEL: {
        GEMINI: 'immediate-or-cancel',
        POLONIEX: 'immediateOrCancel',
        COINBASE: {'time_in_force': 'IOC'},
        KRAKEN: UNSUPPORTED,
        BLOCKCHAIN: 'IOC'
    },
    MAKER_OR_CANCEL: {
        GEMINI: 'maker-or-cancel',
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

    if exchange == POLONIEX:
        if feed not in _feed_to_exchange_map:
            return symbol_std_to_exchange(feed, POLONIEX)
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
    return channel in (ORDER_INFO)
