# CCXT Generic Exchange API Reference

## Configuration Models

> Modules live beneath `cryptofeed/exchanges/ccxt/`. Use package-relative imports such as `from cryptofeed.exchanges.ccxt.config import CcxtConfig`. Compatibility shims exist for legacy paths but new integrations should adopt the package layout.

### `CcxtConfig`
- **Fields**: `exchange_id`, `api_key`, `secret`, `passphrase`, `sandbox`, `rate_limit`, `enable_rate_limit`, `timeout`, `proxies`, `transport`, `options`.
- **Methods**:
  - `to_exchange_config()` → `CcxtExchangeConfig`
  - `to_context(proxy_settings=None)` → `CcxtExchangeContext`

### `CcxtExchangeContext`
- `exchange_id`: Normalized CCXT identifier.
- `ccxt_options`: Dict passed directly to CCXT clients (keys like `apiKey`, `secret`, `timeout`).
- `transport`: `CcxtTransportConfig` (snapshot interval, websocket toggle, rest-only, market-id usage).
- `http_proxy_url` / `websocket_proxy_url`: Resolved strings from explicit config or `ProxySettings` fallback.
- `use_sandbox`: Boolean derived from configuration.

### `CcxtConfigExtensions`
- `register(exchange_id, hook)`: Mutate raw config dictionaries for a specific exchange before validation.
- `reset()`: Clear registered hooks.

### `load_ccxt_config(...)`
```python
load_ccxt_config(
    exchange_id: str,
    yaml_path: Optional[str | Path] = None,
    overrides: Optional[dict] = None,
    proxy_settings: Optional[ProxySettings] = None,
    env: Optional[Mapping[str, str]] = None,
) -> CcxtExchangeContext
```
- YAML ➔ Environment ➔ Overrides precedence.
- Converts raw dictionaries into validated contexts ready for transports and feeds.

### `validate_ccxt_config(...)`
- Backward-compatible helper that accepts legacy dict inputs and returns a `CcxtExchangeConfig` after applying extensions and validation.

## Transport Layer

### `CcxtRestTransport(cache, *, context=None, require_auth=False, auth_callbacks=None)`
- **Responsibilities**: instantiate `ccxt.async_support.<exchange>` with merged options, enforce credential checks, execute registered authentication callbacks, fetch snapshots via `fetch_order_book`.
- **Key Methods**:
  - `_ensure_client()` → ensures CCXT async client is ready with proxy + options.
  - `_authenticate_client(client)` → validates credentials and runs callbacks.
  - `order_book(symbol, limit=None)` → returns `OrderBookSnapshot` dataclass.

### `CcxtWsTransport(cache, *, context=None, require_auth=False, auth_callbacks=None)`
- **Responsibilities**: instantiate `ccxt.pro.<exchange>`, enforce credentials, fetch trade updates via `watch_trades`.
- **Key Methods**:
  - `_ensure_client()` / `_authenticate_client(client)` analogous to REST.
  - `next_trade(symbol)` → returns `TradeUpdate` dataclass with normalized fields; updates `connect_count` / `reconnect_count` and raises `CcxtUnavailable` when websocket support is absent (triggering REST fallback in the generic feed).

## Generic Feed

### `CcxtGenericFeed`
- **Constructor Parameters**: `exchange_id`, `symbols`, `channels`, `snapshot_interval`, `websocket_enabled`, `rest_only`, `metadata_cache`, `rest_transport_factory`, `ws_transport_factory`, `config_context`.
- **Authentication Handling**:
  - Private channels (`balances`, `fills`, `orders`, `order_info`, `order_status`, `positions`, `trade_history`, `transactions`) require contexts with credentials; missing values raise `RuntimeError`.
  - `register_authentication_callback(callable)` to append synchronous/async hooks; called before first authenticated request.
- **Utilities**:
  - `bootstrap_l2` (async) – fetches snapshots via REST transport.
  - `stream_trades_once` (async) – consumes a single `watch_trades` batch.
  - Internal `_create_rest_transport`/`_create_ws_transport` propagate context and auth settings to transport factories.

## Adapter Layer

### `CcxtTradeAdapter`
- Converts CCXT trades to `cryptofeed.types.Trade`, preserving decimals, timestamps, and raw payload.
- Raises `AdapterValidationError` on missing fields; logs errors and returns `None` for invalid payloads.

### `CcxtOrderBookAdapter`
- Converts CCXT order book payloads to `cryptofeed.types.OrderBook` with Decimal precision.
- Extracts sequence numbers from `nonce`/`sequence`/`seq` fields when present.

### `AdapterRegistry`
- `register_trade_adapter(exchange_id, adapter_class)` / `register_orderbook_adapter(exchange_id, adapter_class)` to override defaults per exchange.
- `register_trade_hook(exchange_id, hook)` / `register_orderbook_hook(exchange_id, hook)` attach payload mutators.
- `register_trade_normalizer(exchange_id, field, func)` / `register_orderbook_normalizer(exchange_id, field, func)` override specific normalization steps (symbol, price, timestamp, price levels).
- `convert_trade(exchange_id, payload)` / `convert_orderbook(exchange_id, payload)` execute adapters, hooks, and fallback adapters, returning `None` when the event should be dropped.
- `get_trade_adapter(exchange_id)` / `get_orderbook_adapter(exchange_id)` still expose adapter classes when manual control is required.

### Hook Decorators & Registry
- `ccxt_trade_hook(exchange_id, *, symbol=None, price=None, timestamp=None)` registers a hook and optional normalizers for trade payloads.
- `ccxt_orderbook_hook(exchange_id, *, symbol=None, price_levels=None, timestamp=None)` provides the same for order books.
- `AdapterHookRegistry.reset()` clears all registered hooks (used in unit tests).

## Feed Integration (`CcxtFeed`)
- Accepts `config` (`CcxtExchangeConfig` / `CcxtExchangeContext`) or legacy parameters (`exchange_id`, `proxies`, `ccxt_options`).
- Converts overrides via `load_ccxt_config`, exposing `ccxt_config` / `ccxt_context` attributes on the feed.
- Wires conversions through the adapter registry (hooks + fallbacks) and emits a bootstrap trade when starting to prime callback pipelines.
- `start()` schedules background tasks without blocking; `stop()` cancels tasks, awaits completion, and closes transports cleanly.

## Testing Hooks
- `_dynamic_import` / `_resolve_dynamic_import` helpers in `cryptofeed.exchanges.ccxt.generic` and transport modules can be monkeypatched to supply stub CCXT clients.
- `CcxtGenericFeed.register_authentication_callback` enables instrumentation of credential flows during unit/integration testing.
- `@pytest.mark.ccxt_future` marks deferred sandbox/performance suites (see `tests/integration/test_ccxt_future.py`).

## Exceptions
- `CcxtUnavailable`: Raised when CCXT async/pro modules for the exchange cannot be imported.
- `RuntimeError` (private auth failure): thrown when private channels are requested without valid credentials.
- `AdapterValidationError`: surfaced when adapters encounter malformed payloads.

## Test Modules
- **Unit**: `tests/unit/test_ccxt_config.py`, `tests/unit/test_ccxt_adapters_conversion.py`, `tests/unit/test_ccxt_generic_feed.py`
- **Integration**: `tests/integration/test_ccxt_generic.py`
- **Smoke / E2E**: `tests/integration/test_ccxt_feed_smoke.py`
