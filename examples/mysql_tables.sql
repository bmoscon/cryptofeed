-- candles
CREATE TABLE IF NOT EXISTS candles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    candle_start TIMESTAMP,
    candle_stop TIMESTAMP,
    `interval` VARCHAR(4), 
    trades INTEGER,
    open DECIMAL(64, 30), 
    close DECIMAL(64, 30),
    high DECIMAL(64, 30),
    low DECIMAL(64, 30),
    volume DECIMAL(64, 30),
    closed BOOLEAN
);

-- ticker
CREATE TABLE IF NOT EXISTS ticker (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    bid DECIMAL(64, 30),
    ask DECIMAL(64, 30)
);

-- trades
CREATE TABLE IF NOT EXISTS trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    side VARCHAR(8),
    amount DECIMAL(64, 30),
    price DECIMAL(64, 30),
    trade_id VARCHAR(64),
    order_type VARCHAR(32)
);

-- open interest
CREATE TABLE IF NOT EXISTS open_interest (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    open_interest INTEGER
);

-- index rename market_index, index is keyword
CREATE TABLE IF NOT EXISTS market_index (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    open_interest DOUBLE
);

-- funding
CREATE TABLE IF NOT EXISTS funding (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    mark_price DOUBLE,
    rate DOUBLE,
    next_funding_time TIMESTAMP,
    predicted_rate DOUBLE
);

-- liquidations
CREATE TABLE IF NOT EXISTS liquidations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    side VARCHAR(8),
    quantity DECIMAL(64, 30),
    price DECIMAL(64, 30),
    trade_id VARCHAR(64),
    status VARCHAR(16)
);

CREATE TABLE IF NOT EXISTS l2_book (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP,
    receipt_timestamp TIMESTAMP,
    exchange VARCHAR(32),
    symbol VARCHAR(32),
    data JSON
);

-- custom candles table
CREATE TABLE IF NOT EXISTS custom_candles (
    ts TIMESTAMP,
    received TIMESTAMP,
    exch VARCHAR(32),
    pair VARCHAR(32),
    start TIMESTAMP,
    stop TIMESTAMP,
    o DECIMAL(64, 30),
    h DECIMAL(64, 30),
    l DECIMAL(64, 30),
    c DECIMAL(64, 30),
    v DECIMAL(64, 30),
    closed BOOLEAN
);
