-- ClickHouse Table Creation SQL for Cryptofeed
-- Execute these commands to create the necessary tables for storing cryptofeed data
-- 
-- First, create the database:
-- clickhouse-client --query "CREATE DATABASE IF NOT EXISTS cryptofeed"
--
-- Then run this script:
-- clickhouse-client --database=cryptofeed < clickhouse_tables.sql

-- Trades table
CREATE TABLE IF NOT EXISTS trades
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
CREATE TABLE IF NOT EXISTS ticker
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

-- Book table (stores order book snapshots and deltas as JSON)
CREATE TABLE IF NOT EXISTS book
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
CREATE TABLE IF NOT EXISTS funding
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
CREATE TABLE IF NOT EXISTS open_interest
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
CREATE TABLE IF NOT EXISTS liquidations
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

-- Candles table (OHLCV data)
CREATE TABLE IF NOT EXISTS candles
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
CREATE TABLE IF NOT EXISTS index
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

-- Order Info table (authenticated channel)
CREATE TABLE IF NOT EXISTS order_info
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

-- Fills table (authenticated channel - executed trades)
CREATE TABLE IF NOT EXISTS fills
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

-- Transactions table (authenticated channel - deposits/withdrawals)
CREATE TABLE IF NOT EXISTS transactions
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

-- Balances table (authenticated channel)
CREATE TABLE IF NOT EXISTS balances
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

-- Optional: Create materialized views for common queries
-- Example: Aggregate trade volume by minute
CREATE MATERIALIZED VIEW IF NOT EXISTS trades_by_minute
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (exchange, symbol, minute)
AS SELECT
    exchange,
    symbol,
    toStartOfMinute(timestamp) AS minute,
    sum(amount) AS total_volume,
    count() AS trade_count
FROM trades
GROUP BY exchange, symbol, minute;

-- Example: Latest ticker prices (keeps only the most recent record)
CREATE MATERIALIZED VIEW IF NOT EXISTS latest_ticker
ENGINE = ReplacingMergeTree(receipt_timestamp)
PARTITION BY exchange
ORDER BY (exchange, symbol)
AS SELECT
    exchange,
    symbol,
    timestamp,
    receipt_timestamp,
    bid,
    ask
FROM ticker;
