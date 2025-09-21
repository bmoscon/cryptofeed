# Backpack Exchange Integration (ccxt/ccxt.pro MVP)

## Objectives

- Provide a drop-in `CcxtBackpackFeed` aligned with Cryptofeed's SOLID/KISS principles.
- Support public market data (trades, L2 book) for `BTC/USDT` and `ETH/USDT`.
- Reuse ccxt metadata and ccxt.pro streams while keeping the existing emitter/queue architecture intact.

## Endpoints & Authentication

- REST base: `https://api.backpack.exchange/` (rate limited).
- WebSocket base: `wss://ws.backpack.exchange`.
- Trading pairs follow `<base>_<quote>` convention (e.g., `BTC_USDT`).
- Authenticated REST requires headers: `X-Timestamp`, `X-Window`, `X-API-Key`, `X-Signature` (ED25519).
- Private WebSocket subscriptions sign `{"method": "subscribe", ...}` payloads using the same key.

## Channel Mapping

| Cryptofeed Channel | Backpack Topic | Notes |
|--------------------|----------------|-------|
| TRADES             | `trade.<symbol>` | Stream returns trade ID `t`, price `p`, size `q`, sequence `s`. |
| L2_BOOK            | `depth.<symbol>` | `U/u` fields indicate start/end sequence for delta replay; snapshots via REST. |

## Architecture

```
CcxtBackpackFeed
 ├─ CcxtMetadataCache  -> ccxt.backpack.load_markets()
 ├─ CcxtRestTransport  -> ccxt.async_support.backpack.fetch_order_book()
 └─ CcxtWsTransport    -> ccxt.pro.backpack.watch_trades()/watch_order_book()
```

- Symbol normalization uses ccxt's `safe_symbol`/`market` helpers.
- REST snapshots enqueue L2 events with `force=True` to reset state.
- WebSocket deltas reference `sequence`/`crossSequence` to detect gaps.

## Configuration Example

```yaml
exchanges:
  ccxt_backpack:
    class: Ccxt_Backpack_Feed
    exchange: backpack
    symbols: ["BTC-USDT", "ETH-USDT"]
    channels: [TRADES, L2_BOOK]
    snapshot_interval: 30
    websocket: true
    rest_only: false
    api_key: ${BACKPACK_KEY}      # optional
    api_secret: ${BACKPACK_SECRET}
```

## Error Handling

- Handle HTTP 451 / regional restrictions and expose alternative hosts (e.g., VPN or future regional domains).
- Back off on `429` using ccxt's `rateLimit` and `asyncio.sleep`.
- If WebSocket fails repeatedly, fall back to REST polling until connectivity recovers.

## Testing

1. Unit: mock ccxt transports to assert symbol mapping, emitter integration, and error surfacing.
2. Integration: run against Backpack from allowed region; verify trades/L2 events reach callbacks.
3. Regression: add docker-compose harness to confirm compatibility each release.

## Open Questions

- Confirm microsecond timestamp conversion requirements for downstream storage.
- Evaluate ccxt's current `has` flags for Backpack (some channels marked experimental).
- Coordinate upstream PRs to improve market metadata (tick size, contract specs).
