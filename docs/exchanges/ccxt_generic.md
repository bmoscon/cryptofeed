# CCXT Generic Exchange Developer Guide

## Overview
The `ccxt-generic-pro-exchange` refactor consolidates every CCXT integration primitive under `cryptofeed/exchanges/ccxt/`. Feed developers now work from a single package that exposes typed configuration, proxy-aware transports, adapter hooks, and a builder for dynamic feed classes. Legacy modules remain as shims, but new code should import from the package layout directly.

### Module Map
| Module | Responsibility |
| --- | --- |
| `config.py` | Pydantic models for credentials, proxies, transport knobs |
| `context.py` | Converters + loaders producing `CcxtExchangeContext` |
| `transport/rest.py` | REST snapshots with proxy injection and retry/backoff |
| `transport/ws.py` | CCXT-Pro trades with reconnect counters and REST fallback |
| `adapters/` | Base + concrete adapters, registry, hook decorators |
| `builder.py` | `CcxtExchangeBuilder` for dynamic feed classes |
| `feed.py` | `CcxtFeed` bridge into the `Feed` inheritance tree |

## Getting Started
1. **Install dependencies** – `pip install ccxt ccxtpro` (WebSocket support requires `ccxtpro`).
2. **Describe configuration** – declare a `CcxtConfig` or load via YAML/env using `load_ccxt_config()`.
3. **Instantiate the feed** – construct `CcxtFeed` using a typed context; transports, adapters, and hooks are wired automatically.

```python
from cryptofeed.exchanges.ccxt.config import CcxtConfig
from cryptofeed.exchanges.ccxt.feed import CcxtFeed

config = CcxtConfig(
    exchange_id="backpack",
    api_key="<API_KEY>",
    secret="<API_SECRET>",
    proxies={"rest": "http://proxy:8080", "websocket": "socks5://proxy:1080"},
    transport={"snapshot_interval": 15, "websocket_enabled": True},
)

feed = CcxtFeed(
    config=config.to_exchange_config(),
    symbols=["BTC-USDT"],
    channels=["trades", "l2_book"],
    callbacks={"trades": handle_trade, "l2_book": handle_book},
)
```

## Configuration Sources & Precedence
- **Typed models** – call `CcxtConfig.to_context()` for strongly-typed validation.
- **YAML** – place definitions under `exchanges.<id>` and load with `load_ccxt_config(yaml_path=...)`.
- **Environment** – use `CRYPTOFEED_CCXT_<ID>__FIELD` (double underscores for nesting); values merge via `_deep_merge`.
- **Overrides** – pass dict overrides for CLI/pytest fixtures; overrides take highest precedence.

> Commit guidance: document behaviour with `docs(ccxt): ...`, keep refactors separate from user-visible `feat/fix` commits.

## Authentication & Hooks
- Private channels (`ORDERS`, `FILLS`, `BALANCES`, etc.) require contexts with API key + secret; absence raises `RuntimeError` during feed construction.
- Register additional auth steps via `CcxtGenericFeed.register_authentication_callback()`; callbacks can be async and run for both REST and WebSocket transports.
- Use hook decorators to normalize payloads without modifying core adapters:

```python
from cryptofeed.exchanges.ccxt.adapters import ccxt_trade_hook

@ccxt_trade_hook("backpack", timestamp=lambda ts, raw, payload: ts / 1000)
def normalize_timestamp(payload):
    payload = dict(payload)
    payload["timestamp"] *= 1000
    return payload
```

## Transport Behaviour
- Proxy URLs are resolved from explicit config or the shared proxy injector; transports pass values to CCXT (`aiohttp_proxy`, `proxies`).
- `CcxtWsTransport` tracks reconnect counts; if websockets remain unavailable, the generic feed automatically switches to REST-only mode and logs the fallback.
- Snapshot cadence, websocket toggles, and market ID usage are governed by `CcxtTransportConfig` values inside the context.

## Migration Checklist
1. Update imports to `cryptofeed.exchanges.ccxt.*` modules.
2. Replace bespoke CCXT clients with `CcxtGenericFeed` or `CcxtFeed` using contexts.
3. Register exchange-specific normalization using hook decorators or custom adapters via `AdapterRegistry`.
4. Remove legacy proxy wiring—transports now honour the shared proxy injector by default.
5. Verify no code imports legacy shims (`cryptofeed.exchanges.ccxt_feed`, `ccxt_config`, `ccxt_transport`, `ccxt_adapters`).
6. Run `pytest tests/unit/test_ccxt_* tests/integration/test_ccxt_generic.py -q` to verify coverage.

## Monitoring Legacy Shims
- Shim imports now trigger a `feedhandler` warning and increment counters exposed via `cryptofeed.exchanges.get_shim_usage()`.
- Run `python - <<'PY'
from cryptofeed.exchanges import get_shim_usage
print(get_shim_usage())
PY` to inspect downstream usage during migration reviews.
- Remove remaining shims once counters stay at zero across release cycles (spec `ccxt-generic-pro-exchange` task 7.4).

## Testing Strategy
- **Unit** – `tests/unit/test_ccxt_adapter_registry.py`, `tests/unit/test_ccxt_feed_config_validation.py`, `tests/unit/test_ccxt_generic_feed.py`.
- **Integration** – `tests/integration/test_ccxt_generic.py` validates REST snapshots, WebSocket trades, proxy routing, and REST fallback.
- **Future NFR** – `tests/integration/test_ccxt_future.py` (tagged with `@pytest.mark.ccxt_future`) holds placeholders for sandbox/performance scenarios.

## Troubleshooting
- **Missing credentials** – ensure contexts include `api_key` + `secret`; validation errors surface with helpful messaging.
- **Proxy mismatch** – confirm proxy settings map to the CCXT exchange ID; review feed logs for `proxy:` entries.
- **WebSocket gaps** – monitor `ccxt feed falling back to REST` warnings; switch to `rest_only=True` if the venue lacks realtime support.

## Roadmap & NFR Backlog
- Metrics & telemetry (latency counters, reconnect histograms) will be tackled in a follow-on spec (`ccxt-metrics-harden`).
- Sandbox verification awaits credentials; placeholders live under `tests/integration/test_ccxt_future.py`.
- Proxy pool rotation enhancements align with the `proxy-pool-system` roadmap.

Completion of the FR scope for `ccxt-generic-pro-exchange` is logged; revisit this document when scheduling the next iteration.
