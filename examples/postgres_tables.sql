-- candles
CREATE TABLE IF NOT EXISTS candles (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), candle_start TIMESTAMP, candle_stop TIMESTAMP, interval VARCHAR(4), trades INTEGER, open NUMERIC(64, 32), close NUMERIC(64, 32), high NUMERIC(64, 32), low NUMERIC(64, 32), volume NUMERIC(64, 32), closed BOOLEAN);

--  ticker
CREATE TABLE IF NOT EXISTS ticker (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), bid NUMERIC(64, 32), ask NUMERIC(64, 32));

-- trades
CREATE TABLE IF NOT EXISTS trades (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), side VARCHAR(8), amount NUMERIC(64, 32), price NUMERIC(64, 32), trade_id VARCHAR(64), order_type VARCHAR(32));

-- open interest
CREATE TABLE IF NOT EXISTS open_interest (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), open_interest INTEGER);

-- index
CREATE TABLE IF NOT EXISTS index (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), open_interest DOUBLE PRECISION);

-- funding
CREATE TABLE IF NOT EXISTS funding (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), mark_price DOUBLE PRECISION, rate DOUBLE PRECISION, next_funding_time TIMESTAMP, predicted_rate DOUBLE PRECISION);

-- liquidations
CREATE TABLE IF NOT EXISTS liquidations (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), side VARCHAR(8), quantity NUMERIC(64, 32), price NUMERIC(64, 32), trade_id VARCHAR(64), status VARCHAR(16));

-- book
CREATE TABLE IF NOT EXISTS l2_book (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), data JSONB);

-- custom candles table, used to demonstrate custom_columns in demo_postgres.py
CREATE TABLE IF NOT EXISTS custom_candles (ts TIMESTAMP, received TIMESTAMP, exch VARCHAR(32), pair VARCHAR(32), start TIMESTAMP, stop TIMESTAMP, o NUMERIC(64, 32), h NUMERIC(64, 32), l NUMERIC(64, 32), c NUMERIC(64, 32), v NUMERIC(64, 32), closed BOOLEAN);
