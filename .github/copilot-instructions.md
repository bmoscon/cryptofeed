# Cryptofeed AI Coding Instructions

## Project Overview
Cryptofeed is a normalized cryptocurrency exchange feed handler library that aggregates real-time market data (trades, order books, tickers) from 40+ exchanges via WebSocket and REST APIs, exposing them through a unified callback-based interface.

## Architecture

### Core Components
- **FeedHandler** (`cryptofeed/feedhandler.py`): Main orchestrator managing multiple feeds, async event loop, and lifecycle (startup/shutdown signals)
- **Feed** (`cryptofeed/feed.py`): Per-exchange handler inheriting from Exchange, manages channel subscriptions, reconnection logic, and message parsing
- **Exchange** (`cryptofeed/exchange.py`): Base class defining interface: `websocket_channels`, `rest_endpoints`, symbol mapping, order validation
- **Connection** (`cryptofeed/connection.py`): HTTP/WebSocket client abstractions (`HTTPSync`, `HTTPAsyncConn`, `WSAsyncConn`) with raw data collection hooks
- **Types** (`cryptofeed/types.pyx`): Cython-compiled data classes (Trade, Ticker, OrderBook, Candle, etc.) for performance-critical paths; use `Decimal` for prices

### Data Flow
1. FeedHandler adds feeds → Feed initializes symbol mapping → WebSocket/REST connections open
2. Messages arrive → Feed's channel-specific parser (e.g., `parse_l2_book`) deserializes and normalizes
3. Normalized objects (Trade, Ticker) passed to user-provided async/sync callbacks via Callback wrapper
4. Optional backends (Kafka, Redis, Postgres, etc.) persist data

## Key Patterns & Conventions

### Exchange Implementation
- **Inherit from Feed, not Exchange directly** (Feed extends Exchange)
- Define class attributes:
  - `id = 'EXCHANGE_NAME'` (from `defines.py`)
  - `websocket_endpoints = [WebsocketEndpoint(...)]` / `rest_endpoints = [RestEndpoint(...)]`
  - `websocket_channels = {TRADES: 'channel_name', L2_BOOK: '...'}` (map cryptofeed types to exchange channel names)
- Implement `_parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]` to normalize exchange symbols to Symbol objects
- Implement channel parsers (e.g., `async def _parse_trades(self, msg, receipt_timestamp)`) that deserialize exchange JSON into cryptofeed types
- Use `self.normalized_symbol_mapping` (str → Symbol) for lookups

### Symbol & Type System
- Use `Symbol` objects (not strings) for type safety: `Symbol(base_asset, quote_asset, type=SPOT|FUTURES|PERPETUAL, expiry_date=None)`
- All prices/amounts are `Decimal`, never float (for precision)
- Timestamp normalization: exchanges often send milliseconds; normalize to seconds with `cls.timestamp_normalize()`

### Callbacks & Async Patterns
- Callbacks are user functions called with signature: `callback(data_object, receipt_timestamp)`
- Can be `async def` or sync; wrapper in `Callback` handles execution in executor if needed
- Lightweight callbacks preferred; FeedHandler is paused during callback execution

### Configuration
- Config loaded from `config.yaml` or passed as dict to FeedHandler/Exchange constructors
- API keys stored under exchange IDs in lowercase (e.g., `config['binance']` with `.key_id`, `.key_secret`, `.key_passphrase`)
- Supports sandbox mode via `sandbox=True` parameter

## Developer Workflow

### Testing
- Run unit tests: `pytest tests/unit/` 
- Integration tests with live API: `pytest tests/integration/` (requires API keys)
- No formal test suite runner; use pytest directly

### Code Style & Linting
- **Type annotations required** on public methods (see existing exchanges for examples)
- Prefer long lines (130+ chars) over line wrapping; isort for import formatting
- Run `flake8` before PRs to catch style issues
- Import order: stdlib → third-party → `cryptofeed`

### Adding an Exchange
1. Create `cryptofeed/exchanges/new_exchange.py`
2. Implement Feed subclass with required attributes and parsers
3. Add sample data file in `sample_data/` for testing (format: `EXCHANGE_NAME.0`, `EXCHANGE_NAME.ws.1.0`)
4. Update `cryptofeed/exchanges/__init__.py` to export the class
5. Reference API docs in PR; include link in README

### Cython Types
- `types.pyx` compiled with `cythonize` in setup.py; edit as `.pyx`, not `.py`
- Use `@cython.freelist(n)` for frequently allocated types (Trade, Candle)
- Compile with: `python setup.py build_ext --inplace`

### Backend Implementation
"Backends" in cryptofeed are not just database connectors—they're **callback wrappers** (middleware) that can aggregate, transform, persist, or format data from any channel. They follow two patterns:

**Pattern 1: Data Persistence** (e.g., Kafka, Postgres, Redis)
- Inherit from a base backend class or implement async callback interface
- Implement `async def __call__(self, data, receipt_timestamp)` to receive normalized objects (Trade, Ticker, OrderBook, etc.)
- Batch/buffer writes for efficiency; handle connection lifecycle (start/stop)
- Example: `cryptofeed/backends/kafka.py` buffers trades and flushes to Kafka

**Pattern 2: Data Transformation/Aggregation** (e.g., OHLCV, Throttle, Renko)
- Inherit from `AggregateCallback` in `cryptofeed/backends/aggregate.py`
- Wrap and chain to other handlers: `self.handler(data, receipt_timestamp)`
- Aggregate across time windows or price movements before forwarding
- Example: `Throttle` allows 1 callback per time window; `OHLCV` aggregates trades into OHLCV bars

**Adding a Backend:**
1. Create `cryptofeed/backends/my_backend.py`
2. Implement class with `async def __call__(self, data, receipt_timestamp)` 
3. Optional: add `start()` and `stop()` lifecycle methods for resource management
4. Pass to FeedHandler: `fh.add_feed(Exchange(..., callbacks={TRADES: MyBackend(...), TICKER: MyBackend(...)}))`
5. Backend receives each data type independently; use `hasattr(data, 'attribute')` to handle multiple types if needed

### Import Structure
- Exchange-specific symbols mapped through `cryptofeed/defines.py` (BINANCE, KRAKEN, etc.)
- Channel constants: L2_BOOK, L3_BOOK, TRADES, TICKER, FUNDING, LIQUIDATIONS, CANDLES, etc.
- Callback types in `callback.py` (TradeCallback, TickerCallback, etc.)

## Cross-Component Communication
- **Symbol resolution**: Feed queries Symbols registry (singleton) to map exchange symbols ↔ normalized formats
- **Raw data collection**: Optional raw_data_callback on Connection class intercepts ALL HTTP/WebSocket traffic for debugging
- **Backends**: Decouple data persistence; passed as callbacks (e.g., KafkaBackend implements async write logic)
- **NBBO**: Synthetic feed aggregating best bids/asks across multiple exchanges (see `nbbo.py` and `examples/demo_nbbo.py`)

## Common Pitfalls
- Forgetting `async def` on parsers that call I/O operations
- Using float for prices instead of Decimal → precision loss
- Not normalizing exchange timestamps to UTC seconds
- Missing `checkpoint_validation` or `cross_check` flags for exchanges with weak message ordering
- Hardcoding depth limits instead of checking exchange's `valid_depths` parameter

## Quick Reference Files
- Channel definitions: `cryptofeed/defines.py`
- Callback signatures: `cryptofeed/callback.py`
- Example integration: `examples/demo.py`, `examples/demo_binance_authenticated.py`
- Configuration template: `config.yaml`
- Documentation index: `docs/README.md`
