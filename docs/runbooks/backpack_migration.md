# Backpack Native Feed Verification Runbook

## Goals
- Confirm native `BackpackFeed` operation following removal of the legacy
  `CcxtBackpackFeed` adapter.
- Validate ED25519 authentication, proxy routing, and normalized data flow.
- Ensure observability dashboards and alerts cover the native feed metrics.

## Prerequisites
- Deploy a release dated October 2025 or later (native feed registered by
  default).
- Provide ED25519 credentials (API key, public key, private seed, optional
  passphrase) via `BackpackConfig`.
- Configure proxy settings globally or through `BackpackConfig.proxies` if
  exchange-specific overrides are required.
- Access to recorded fixtures (`tests/fixtures/backpack/`) for dry-run testing.

## Verification Steps
1. **Sandbox Validation**
   - Run `pytest tests/integration/test_backpack_native.py` against fixtures or
     sandbox endpoints.
   - Execute `python -m tools.backpack_auth_check` with staged credentials to
     confirm key format and timestamp window alignment.

2. **Staging Readiness**
   - Launch a FeedHandler instance with `BackpackFeed` configured via
     `BackpackConfig`.
   - Inspect `feed.metrics_snapshot()` for message throughput and absence of
     errors.
   - Call `feed.health(max_snapshot_age=30)` and verify `status == "healthy"`.

3. **Production Rollout**
   - Deploy updated configuration referencing `BACKPACK` (no feature flag
     required).
   - Monitor key metrics: `backpack.ws.reconnects`, `backpack.ws.auth_failures`,
     `backpack.parser.errors`, and proxy rotation counters.
   - Validate downstream consumers receive normalized symbols (`BTC-USDT`) and
     consistent sequencing.

## Incident Response
- If persistent auth failures occur, inspect ED25519 key material and ensure
  system clocks are synchronized (microsecond precision required).
- For proxy-related disconnects, review proxy injector health metrics and
  rotate pool entries as documented in `docs/proxy/runbooks`.
- In case of severe regression, disable Backpack subscriptions temporarily (do
  not revert to ccxt) and engage exchange support while analysing captured
  payloads.

## Success Criteria
- `BackpackFeed.health().healthy` reports `True` across observation windows.
- No increase in downstream error rates or alert volume.
- Private channel callbacks fire with valid ED25519 signatures and timestamps.

## References
- `docs/exchanges/backpack.md` – configuration, observability, and proxy
  guidance.
- `docs/migrations/backpack_ccxt.md` – historical record of ccxt deprecation.
