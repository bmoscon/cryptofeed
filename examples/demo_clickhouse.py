'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.clickhouse import (
    TradeClickHouse, TickerClickHouse, BookClickHouse, 
    CandlesClickHouse, FundingClickHouse, OpenInterestClickHouse
)
from cryptofeed.defines import CANDLES, FUNDING, L2_BOOK, OPEN_INTEREST, TRADES, TICKER
from cryptofeed.exchanges import Bitfinex, Bitmex, Coinbase, Gemini, Binance


def main():
    """
    Before running this example, you need to:
    1. Install ClickHouse: https://clickhouse.com/docs/en/install
    2. Install the ClickHouse Python client: pip install clickhouse-connect
    3. Create the database: clickhouse-client --query "CREATE DATABASE IF NOT EXISTS cryptofeed"
    4. Create the tables using the SQL schema below
    """
    
    # Configure ClickHouse connection
    clickhouse_config = {
        'host': '127.0.0.1',
        'port': 8123,
        'user': 'default',
        'password': '',
        'db': 'cryptofeed'
    }
    
    config = {
        'log': {'filename': 'clickhouse-demo.log', 'level': 'INFO'},
        'backend_multiprocessing': True
    }
    
    f = FeedHandler(config=config)
    
    # Add feeds with ClickHouse backends
    f.add_feed(Bitmex(
        channels=[TRADES, FUNDING, OPEN_INTEREST],
        symbols=['BTC-USD-PERP'],
        callbacks={
            TRADES: TradeClickHouse(**clickhouse_config),
            FUNDING: FundingClickHouse(**clickhouse_config),
            OPEN_INTEREST: OpenInterestClickHouse(**clickhouse_config)
        }
    ))
    
    f.add_feed(Bitfinex(
        channels=[TRADES],
        symbols=['BTC-USD'],
        callbacks={TRADES: TradeClickHouse(**clickhouse_config)}
    ))
    
    f.add_feed(Coinbase(
        config=config,
        channels=[TRADES, TICKER],
        symbols=['BTC-USD'],
        callbacks={
            TRADES: TradeClickHouse(**clickhouse_config),
            TICKER: TickerClickHouse(**clickhouse_config)
        }
    ))
    
    f.add_feed(Coinbase(
        channels=[L2_BOOK],
        symbols=['BTC-USD'],
        callbacks={L2_BOOK: BookClickHouse(**clickhouse_config, snapshots_only=True)}
    ))
    
    f.add_feed(Gemini(
        symbols=['BTC-USD'],
        callbacks={TRADES: TradeClickHouse(**clickhouse_config)}
    ))
    
    f.add_feed(Binance(
        candle_closed_only=True,
        symbols=['BTC-USDT'],
        channels=[CANDLES],
        callbacks={CANDLES: CandlesClickHouse(**clickhouse_config)}
    ))
    
    f.add_feed(Binance(
        max_depth=10,
        symbols=['BTC-USDT'],
        channels=[L2_BOOK],
        callbacks={L2_BOOK: BookClickHouse(**clickhouse_config, snapshots_only=True)}
    ))

    f.run()


if __name__ == '__main__':
    main()


"""
ClickHouse Table Creation SQL:

-- Trades table
CREATE TABLE IF NOT EXISTS cryptofeed.trades
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    side String,
    amount Float64,
    price Float64,
    id Nullable(String),
    type Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Ticker table
CREATE TABLE IF NOT EXISTS cryptofeed.ticker
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    bid Float64,
    ask Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Book table
CREATE TABLE IF NOT EXISTS cryptofeed.book
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    data String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Funding table
CREATE TABLE IF NOT EXISTS cryptofeed.funding
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    mark_price Nullable(Float64),
    rate Float64,
    next_funding_time Nullable(DateTime64(3)),
    predicted_rate Nullable(Float64)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Open Interest table
CREATE TABLE IF NOT EXISTS cryptofeed.open_interest
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    open_interest Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Liquidations table
CREATE TABLE IF NOT EXISTS cryptofeed.liquidations
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    side String,
    quantity Float64,
    price Float64,
    id String,
    status String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Candles table
CREATE TABLE IF NOT EXISTS cryptofeed.candles
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    start DateTime64(3),
    stop DateTime64(3),
    interval String,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    closed Nullable(Bool)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, start)
SETTINGS index_granularity = 8192;

-- Index table
CREATE TABLE IF NOT EXISTS cryptofeed.index
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    price Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Order Info table
CREATE TABLE IF NOT EXISTS cryptofeed.order_info
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    id String,
    client_order_id Nullable(String),
    side String,
    status String,
    type String,
    price Nullable(Float64),
    amount Float64,
    remaining Nullable(Float64),
    account Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Fills table
CREATE TABLE IF NOT EXISTS cryptofeed.fills
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    symbol String,
    price Float64,
    amount Float64,
    side String,
    fee Nullable(String),
    id String,
    order_id String,
    liquidity Nullable(String),
    type String,
    account Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, timestamp)
SETTINGS index_granularity = 8192;

-- Transactions table
CREATE TABLE IF NOT EXISTS cryptofeed.transactions
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    currency String,
    type String,
    status String,
    amount Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, timestamp)
SETTINGS index_granularity = 8192;

-- Balances table
CREATE TABLE IF NOT EXISTS cryptofeed.balances
(
    timestamp DateTime64(3),
    receipt_timestamp DateTime64(3),
    exchange String,
    currency String,
    balance Float64,
    reserved Float64
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, currency, timestamp)
SETTINGS index_granularity = 8192;
"""
