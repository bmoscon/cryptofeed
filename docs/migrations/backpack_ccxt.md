# Backpack ccxt Adapter Deprecation Checklist (Completed)

All tasks below were completed as part of the October 2025 release that removed
`CcxtBackpackFeed` from production.

## Pre-GA
- [x] Feature flag remained `false` by default until readiness was confirmed.
- [x] Native feed integration tests executed in CI.
- [x] Operator training covered native configuration, metrics, and health checks.
- [x] `tools/backpack_auth_check.py` distributed to support teams.

## GA Readiness
- [x] Release notes announced native feed availability and migration plan.
- [x] Downstream services migrated to native-normalised symbols (`BTC-USDT`).
- [x] Observability dashboards now include Backpack metrics.
- [x] Baseline performance snapshots captured for comparison.

## Rollout
- [x] Canary environments validated the native feed.
- [x] Shadow mode parity confirmed (see updated runbook).
- [x] Production deployments now default to the native feed (feature flag removed).
- [x] 24-hour monitoring completed with healthy metrics.

## Post-GA Cleanup
- [x] Removed `cryptofeed/exchanges/backpack_ccxt.py` and related tests.
- [x] Deleted ccxt-specific fixtures and documentation references.
- [x] Updated `docs/exchange.md` to point exclusively to the native feed.
- [x] Closed the tracking issue linked to this checklist.
