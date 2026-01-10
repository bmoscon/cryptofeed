# ClickHouse Backend for Cryptofeed

This backend enables storing real-time cryptocurrency market data in [ClickHouse](https://clickhouse.com/), a high-performance column-oriented database management system designed for analytics.

## Why ClickHouse?

ClickHouse is ideal for storing time-series data from cryptocurrency exchanges because:

- **Column-oriented storage**: Optimized for analytical queries on large datasets
- **High compression**: Typical compression ratios of 10-15x reduce storage costs
- **Real-time analytics**: Generate reports on billions of rows with subsecond latency
- **Time-series optimized**: Built-in functions for time-based aggregations
- **Horizontal scaling**: Add nodes to scale write and query throughput

## Quick Start

Install Cryptofeed with ClickHouse support

```bash
pip install cryptofeed[clickhouse]
```

Create the dataabase

```bash
clickhouse-client --query "CREATE DATABASE IF NOT EXISTS cryptofeed"
```

Create tables using the provided schema

```bash
clickhouse-client --database=cryptofeed < examples/clickhouse_tables.sql
```

## Usage

```python
from cryptofeed import FeedHandler
from cryptofeed.backends.clickhouse import TradeClickHouse, BookClickHouse
from cryptofeed.defines import TRADES, L2_BOOK
from cryptofeed.exchanges import Coinbase

def main():
    clickhouse_config = {
        'host': '127.0.0.1',
        'port': 8123,  # HTTP interface port
        'user': 'default',
        'password': '',
        'db': 'cryptofeed'
    }
    
    f = FeedHandler()
    f.add_feed(Coinbase(
        channels=[TRADES, L2_BOOK],
        symbols=['BTC-USD'],
        callbacks={
            TRADES: TradeClickHouse(**clickhouse_config),
            L2_BOOK: BookClickHouse(**clickhouse_config, snapshots_only=True)
        }
    ))
    f.run()

if __name__ == '__main__':
    main()
```

## Supported Data Types

All cryptofeed data types are supported:

- **Market Data**: `TradeClickHouse`, `TickerClickHouse`, `BookClickHouse`, `CandlesClickHouse`, `FundingClickHouse`, `OpenInterestClickHouse`, `LiquidationsClickHouse`, `IndexClickHouse`
- **Authenticated**: `OrderInfoClickHouse`, `FillsClickHouse`, `TransactionsClickHouse`, `BalancesClickHouse`

## Schema Design

The default schema uses ClickHouse best practices:

- **MergeTree engine**: Optimized for inserts and range queries
- **Partitioning by month**: `PARTITION BY toYYYYMM(timestamp)` enables efficient data management
- **Sorting key**: `ORDER BY (exchange, symbol, timestamp)` optimizes queries filtering by these columns
- **DateTime64(3)**: Millisecond precision timestamps

## Custom Columns

You can customize column names and selectively store fields:

```python
custom_columns = {
    'symbol': 'instrument',
    'price': 'trade_price',
    'amount': 'volume',
    'side': 'direction'
}

TradeClickHouse(**clickhouse_config, custom_columns=custom_columns)
```

## Example Queries

### Recent trades for BTC-USD

```sql
SELECT timestamp, exchange, price, amount, side
FROM trades
WHERE symbol = 'BTC-USD'
ORDER BY timestamp DESC
LIMIT 100;
```

### Volume by exchange and hour

```sql
SELECT 
    toStartOfHour(timestamp) AS hour,
    exchange,
    sum(amount) AS volume,
    count() AS trade_count
FROM trades
WHERE symbol = 'BTC-USD'
  AND timestamp >= now() - INTERVAL 24 HOUR
GROUP BY hour, exchange
ORDER BY hour DESC, exchange;
```

### Price OHLCV aggregation (1-minute candles)

```sql
SELECT 
    toStartOfMinute(timestamp) AS minute,
    exchange,
    symbol,
    argMin(price, timestamp) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, timestamp) AS close,
    sum(amount) AS volume,
    count() AS trades
FROM trades
WHERE symbol = 'BTC-USD'
  AND timestamp >= now() - INTERVAL 1 HOUR
GROUP BY minute, exchange, symbol
ORDER BY minute DESC;
```

### Spread analysis across exchanges

```sql
SELECT 
    timestamp,
    exchange,
    symbol,
    ask - bid AS spread,
    (ask - bid) / bid * 100 AS spread_pct
FROM ticker
WHERE symbol = 'BTC-USD'
  AND timestamp >= now() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;
```

## Performance Tips

1. **Batch inserts**: The backend automatically batches writes for efficiency
2. **Use materialized views**: Pre-aggregate common queries (see examples in clickhouse_tables.sql)
3. **Partition management**: Drop old partitions to manage storage: `ALTER TABLE trades DROP PARTITION '202401'`
4. **Compression codecs**: Add compression for specific columns: `price Float64 CODEC(Delta, ZSTD)`
5. **Projections**: Create alternative sort orders for different query patterns

## Monitoring

View table sizes and compression:

```sql
SELECT 
    table,
    formatReadableSize(sum(bytes)) AS size,
    formatReadableSize(sum(bytes_on_disk)) AS compressed,
    sum(rows) AS rows
FROM system.parts
WHERE database = 'cryptofeed'
  AND active
GROUP BY table;
```

## See Also

- Full example: [examples/demo_clickhouse.py](../examples/demo_clickhouse.py)
- Table schemas: [examples/clickhouse_tables.sql](../examples/clickhouse_tables.sql)
- ClickHouse documentation: <https://clickhouse.com/docs>
