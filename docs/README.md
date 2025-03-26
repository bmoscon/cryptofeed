## Cryptofeed Documentation

* [High level](high_level.md)
* [Data Types](dtypes.md)
* [Callbacks](callbacks.md)
* [Adding a new exchange](exchange.md)
* [Data Integrity for Orderbooks](book_validation.md)
* [Configuration](config.md)
* [Authenticated Channels](auth_channels.md)
* [Performance Considerations](performance.md)
* [REST endpoints](rest.md)
* [ClickHouse Backend](clickhouse_backend.md)

## ClickHouse Backend

The ClickHouse backend allows you to store data in a ClickHouse database. It supports various data types such as trades, funding, ticker, open interest, liquidations, candles, order info, transactions, balances, and fills.

### Example

```python
from cryptofeed import FeedHandler
from cryptofeed.backends.clickhouse import TradeClickHouse, FundingClickHouse

fh = FeedHandler()

# Add ClickHouse backend
fh.add_backend(TradeClickHouse(database='cryptofeed', table='trades'))
fh.add_backend(FundingClickHouse(database='cryptofeed', table='funding'))

fh.run()
```
