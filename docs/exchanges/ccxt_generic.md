# CCXT Generic Exchange Developer Guide

## Overview
The CCXT generic exchange abstraction standardizes how CCXT-backed markets are onboarded into Cryptofeed. This guide walks platform engineers through configuration, authentication, and extension points for building exchange integrations that reuse the shared transports and adapters delivered by the `ccxt-generic-pro-exchange` spec.

## Getting Started
1. **Enable CCXT dependencies**: Install `ccxt` and `ccxtpro` (if WebSocket streams are required) in the runtime environment.
2. **Create configuration**: Use the `CcxtConfig` model or YAML/env sources to define API credentials, proxy routing, rate limits, and transport options.
3. **Instantiate feed**: Construct a `CcxtFeed` with desired symbols/channels. The feed automatically provisions `CcxtGenericFeed` transports and adapters using the supplied configuration context.

```python
from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.feed import CcxtFeed

ccxt_config = CcxtConfig(
    exchange_id="backpack",
    api_key="<API_KEY>",
    secret="<API_SECRET>",
    proxies={
        "rest": "http://proxy.local:8080",
        "websocket": "socks5://proxy.local:1080",
    }
)

feed = CcxtFeed(
    config=ccxt_config.to_exchange_config(),
    symbols=["BTC-USDT"],
    channels=["trades", "l2_book"],
    callbacks={"trades": trade_handler, "l2_book": book_handler},
)
```

## Configuration Sources
- **Pydantic models**: `CcxtConfig` -> `CcxtExchangeContext` ensures strongly-typed fields and validation.
- **YAML**: Place structured config under `exchanges.<id>` and load with `load_ccxt_config(...)`.
- **Environment variables**: Use `CRYPTOFEED_CCXT_<ID>__FIELD` naming (double underscores for nesting).
- **Overrides**: Pass dicts (e.g., CLI options) to `load_ccxt_config(overrides=...)` to merge with YAML/env values.

The loader enforces precedence: overrides ⟶ environment ⟶ YAML ⟶ defaults.

## Authentication & Private Channels
- Channels in `cryptofeed.defines` such as `ORDERS`, `FILLS`, `BALANCES`, and `POSITIONS` trigger private-mode validation.
- The feed requires `apiKey` + `secret`; missing credentials raise runtime errors before network activity.
- Custom auth flows (e.g., sub-account selection) can register coroutines via `CcxtGenericFeed.register_authentication_callback` and inspect/augment the underlying CCXT client before requests begin.

## Proxy & Transport Behaviour
- Proxy settings come from the shared `ProxySettings` (feature-flagged by `CRYPTOFEED_PROXY_*`). If explicit proxies are omitted, the loader pulls defaults per exchange from the proxy system.
- The transport layer propagates proxy URLs to both `aiohttp` and CCXT’s internal proxy fields to ensure REST and WebSocket flows share routing.
- Transport options (`snapshot_interval`, `websocket_enabled`, `rest_only`, `use_market_id`) live inside the `CcxtTransportConfig` model and automatically shape feed behaviour.

> **Directory Layout**: All CCXT modules now live under `cryptofeed/exchanges/ccxt/`. Legacy imports such as `cryptofeed.exchanges.ccxt_config` continue to function via compatibility shims but new development should target the package modules directly.

## Extension Points
- **Symbol normalization**: Override via `CcxtExchangeBuilder.create_feed_class(symbol_normalizer=...)` or subclass `CcxtTradeAdapter` / `CcxtOrderBookAdapter` to handle bespoke payloads.
- **Authentication callbacks**: Register callbacks for token exchange, custom headers, or logging instrumentation.
- **Adapter registry**: Use `AdapterRegistry.register_trade_adapter` to plug exchange-specific converters without changing core code.

## Testing Strategy
- **Unit**: `tests/unit/test_ccxt_config.py`, `tests/unit/test_ccxt_adapters_conversion.py`, `tests/unit/test_ccxt_generic_feed.py` cover configuration precedence, adapter precision, and generic feed authentication/proxy handling via deterministic fakes.
- **Integration**: `tests/integration/test_ccxt_generic.py` patches CCXT async/pro modules to validate combined REST+WebSocket lifecycles, proxy routing, and authentication callbacks without external network calls.
- **Smoke / E2E**: `tests/integration/test_ccxt_feed_smoke.py` drives `FeedHandler` end-to-end (config → start → callbacks) to ensure FeedHandler interoperability, proxy propagation, and authenticated channel flows.

## Troubleshooting
- **Credential errors**: Check that `api_key` and `secret` are set in either the model, environment, or YAML. Missing values surface as `RuntimeError` during transport authentication.
- **Proxy mismatch**: Verify `ProxySettings.enabled` and ensure the exchange ID matches keys in the proxy config so the loader can resolve overrides.
- **Missing symbols**: Populate CCXT metadata via `CcxtMetadataCache.ensure()` before streaming; the feed handles this automatically during `_initialize_ccxt_feed()`.

## Next Steps
- Extend unit/integration tests when onboarding new CCXT exchanges.
- Document exchange-specific quirks in spec-specific folders (e.g., `docs/exchanges/backpack.md`).
- Coordinate with the proxy service specs to enable rotation or sticky sessions once those features are implemented.
