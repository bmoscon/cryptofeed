# Generic ccxt/ccxt.pro Exchange Adapter (MVP)

## Purpose

- Provide a reusable `CcxtGenericFeed` that can power long-tail exchanges via
  ccxt (REST) and ccxt.pro (WebSocket) while respecting Cryptofeed's
  SOLID/KISS/DRY principles.
- Offer configuration hooks for symbol/endpoint overrides so concrete feeds like
  Backpack can extend the base without duplicating code.

## Architecture Outline

```
CcxtGenericFeed
 ├─ CcxtMetadataCache(exchange_id)
 ├─ CcxtRestTransport(exchange_id)
 ├─ CcxtWsTransport(exchange_id)
 └─ CcxtEmitter / queue integration
```

- `exchange_id` (e.g., `backpack`, `binanceus`) drives ccxt dynamic imports.
- Symbol normalization delegates to ccxt markets; derived feeds can override.
- Rest/WS transports expose async context managers for snapshot + streaming.

## Configuration Schema

```yaml
exchanges:
  ccxt_generic:
    class: CcxtGenericFeed
    exchange: backpack
    symbols: ["BTC-USDT"]
    channels: [TRADES, L2_BOOK]
    rest:
      snapshot_interval: 30
      limit: 100
    websocket:
      enabled: true
      rest_only: false
    credentials:
      api_key: ${API_KEY:?}
      api_secret: ${API_SECRET:?}
    endpoints:
      rest: https://api.backpack.exchange
      websocket: wss://ws.backpack.exchange
```

## MVP Scope

1. Support TRADES + L2_BOOK for ccxt exchanges that expose `fetch_order_book`
   and `watch_trades` / `watch_order_book`.
2. Provide HTTP 451/429 handling with configuration for alternative hosts.
3. Use existing queue/emitter, metrics, and backoff logic to avoid duplication (DRY).

## TDD Plan

1. **Unit** – mock ccxt modules to verify metadata caches, transport behaviour,
   and feed orchestration using the Backpack scaffolding as a template.
2. **Integration** – run smoke tests against a ccxt sandbox or permissive
   endpoint (e.g., Binance US) to confirm snapshots and deltas flow.
3. **Regression** – add optional docker-compose harness using ccxt exchanges
   with permissive APIs.

## Engineering Checklist

- SOLID: ccxt-specific code isolated in dedicated modules, feed remains thin.
- KISS: only implement features needed for TRADES/L2_BOOK in MVP; defer
  advanced auth or derivatives until justified.
- DRY: share metadata/transport logic across derived feeds; no duplicated rate
  limit logic.
- YAGNI: defer private/auth channels; keep configuration surface minimal.

