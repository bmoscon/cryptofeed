-- Candles
CREATE TABLE IF NOT EXISTS candles (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), candle_start TIMESTAMP, candle_stop TIMESTAMP, interval VARCHAR(4), trades INTEGER, open NUMERIC(64, 32), close NUMERIC(64, 32), high NUMERIC(64, 32), low NUMERIC(64, 32), volume NUMERIC(64, 32), closed BOOLEAN);

--  ticker
CREATE TABLE IF NOT EXISTS ticker (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), bid NUMERIC(64, 32), ask NUMERIC(64, 32));

-- trades
CREATE TABLE IF NOT EXISTS trades (id serial PRIMARY KEY, timestamp TIMESTAMP, receipt_timestamp TIMESTAMP, exchange VARCHAR(32), symbol VARCHAR(32), side VARCHAR(8), amount NUMERIC(64, 32), price NUMERIC(64, 32), trade_id varchar(32), order_type VARCHAR(32));
