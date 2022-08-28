CREATE DATABASE IF NOT EXISTS cryptofeed

CREATE TABLE IF NOT EXISTS cryptofeed.candles (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, candle_start TIMESTAMP, candle_stop TIMESTAMP, interval String, trades Nullable(INTEGER), open Float64, close Float64, high Float64, low Float64, volume Float64, closed Nullable(UInt8)) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.ticker (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, bid Float64, ask Float64) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.trades (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, side String, amount Float64, price Float64, trade_id Nullable(String), order_type Nullable(String)) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.open_interest (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, open_interest Int32) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.index (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, open_interest DOUBLE) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.funding (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, mark_price DOUBLE, rate DOUBLE, next_funding_time TIMESTAMP, predicted_rate DOUBLE) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.liquidations (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, side String, quantity Float64, price Float64, trade_id String, status String) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.l2_book (id UUID, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange String, symbol String, data String) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);

CREATE TABLE IF NOT EXISTS cryptofeed.custom_candles (id UUID, ts TIMESTAMP, received TIMESTAMP, exch String, pair String, start TIMESTAMP, stop TIMESTAMP, o Float64, c Float64, h Float64, l Float64, v Float64, closed Nullable(UInt8)) ENGINE = MergeTree() PRIMARY KEY(id) ORDER BY (id);