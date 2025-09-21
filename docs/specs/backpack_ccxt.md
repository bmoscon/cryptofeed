# Backpack Exchange Integration (ccxt/ccxt.pro MVP)

## Objectives

- Provide a drop-in `CcxtBackpackFeed` that follows Cryptofeed’s SOLID/KISS architecture.
- Support public market data (TRADES, L2_BOOK) for `BTC/USDT` and `ETH/USDT` in the MVP.
- Reuse ccxt metadata and ccxt.pro streams while retaining existing emitter/queue/backpressure components.

## Endpoints & Authentication

- REST base: `https://api.backpack.exchange/`
- WebSocket base: `wss://ws.backpack.exchange`
- Symbols use `<base>_<quote>` (e.g., `BTC_USDT`).
- Authenticated REST headers: `X-Timestamp`, `X-Window`, `X-API-Key`, `X-Signature` (ED25519).
- Private WebSocket subscriptions sign `{"method": "subscribe", ...}` payloads with the same credentials.

## Channel Mapping & Normalization

| Cryptofeed Channel | Backpack Topic      | Notes |
|--------------------|---------------------|-------|
| TRADES             | `trade.<symbol>`    | Fields: price `p`, quantity `q`, trade id `t`, sequence `s`, timestamp `ts` (µs). |
| L2_BOOK            | `depth.<symbol>`    | Fields: bids/asks arrays plus `U/u` sequence range for deltas. |

Additional transformations:

- Convert timestamps `ts` (µs) → float seconds.
- Normalize symbol via ccxt `safe_symbol` / `market` helpers.
- Preserve `sequence` in event metadata for gap detection.

## Architecture

```
CcxtBackpackFeed
 ├─ CcxtMetadataCache   → ccxt.backpack.load_markets()
 ├─ CcxtRestTransport   → ccxt.async_support.backpack.fetch_order_book()
 └─ CcxtWsTransport     → ccxt.pro.backpack.watch_trades()/watch_order_book()
      ↳ CcxtEmitter     → existing BackendQueue/IggyMetrics
```

- REST snapshots enqueue L2 events with `force=True`, mirroring native connectors (e.g., Binance).
- WebSocket deltas rely on `sequence` / `U/u` to ensure ordered replay.
- Rate limits leverage `exchange.rateLimit` and ccxt’s async throttling helpers.

## Configuration Example

```yaml
exchanges:
  ccxt_backpack:
    class: CcxtBackpackFeed
    exchange: backpack
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    snapshot_interval: 30          # seconds between REST snapshots
    websocket: true                 # disable if region restrictions block WS
    rest_only: false
    api_key: ${BACKPACK_KEY}        # optional for private channels
    api_secret: ${BACKPACK_SECRET}
```

## Error Handling

- Surface HTTP 451 / restricted-location errors and allow alternate endpoints (VPN or future regional hosts).
- Back off on HTTP 429 using ccxt’s built-in rate limit helpers.
- Provide a `rest_only` toggle when WebSocket connectivity repeatedly fails.
- Monitor `exchange.has` flags; log warnings when ccxt marks Backpack features as experimental.

## Testing Strategy

1. **Unit** – mock ccxt transports to assert symbol normalization, queue integration, and error surfacing.
2. **Integration** – run against Backpack from an allowed region; verify trades/L2 callbacks receive sequenced updates.
3. **Regression** – add a docker-compose harness to ensure the ccxt adapter continues to work across releases.

Suggested integration checklist:

- Configure ccxt credentials or VPN endpoint permitted by Backpack.
- Run a short session that bootstraps snapshots (`bootstrap_l2`) and streams trades.
- Record sample payloads (trade + depth delta) for inclusion in regression fixtures.


## Open Questions

- Confirm microsecond timestamp handling for downstream storage/metrics.
- Track ccxt upstream status for Backpack (e.g., futures/spot coverage, precision
  metadata) and contribute fixes where needed.
- Evaluate auth requirements for private channels once order execution streams are in scope.

## Task Breakdown

1. **Metadata cache & symbol normalization** (est. 1 day)
   - Implement `CcxtMetadataCache` wrapper that loads markets and exposes symbol
     conversion helpers (`safe_symbol`, precision info).
   - Map normalized `BTC-USDT` input to Backpack’s `BTC_USDT` identifiers.

2. **REST snapshot adapter** (est. 1 day)
   - Implement `CcxtRestTransport` with `fetch_order_book` bootstrapping,
     including rate-limit backoff.
   - Normalize snapshot payloads and enqueue as `L2_BOOK` events via existing
     emitter logic.

3. **WebSocket transport** (est. 2 days)
   - Implement `CcxtWsTransport` wrapping `watch_trades` and `watch_order_book`.
   - Maintain local sequence state to detect gaps; emit warnings/recover by
     triggering REST snapshot when sequence discontinuity occurs.

4. **Feed integration** (est. 1 day)
   - Wire transports into `CcxtBackpackFeed`, respecting Cryptofeed’s queue and
     metrics patterns (SOLID/KISS).
   - Add configuration parsing (`snapshot_interval`, `rest_only`, credentials).

5. **Error handling & testing hooks** (est. 1 day)
   - Surface HTTP 451/429 errors with actionable messages.
   - Provide toggles for REST-only fallback and alternative hosts.
   - Add unit tests (mocked transports) and integration harness using ccxt
     sandbox credentials (if available).

6. **Documentation & rollout** (est. 0.5 day)
   - Update README/roadmap with ccxt adapter status once MVP lands.
   - Document configuration examples and known caveats (rate limits, region access).
