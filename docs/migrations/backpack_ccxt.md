# Backpack ccxt Adapter Deprecation Checklist

## Pre-GA
- [ ] Feature flag remains `false` by default in production deployments.
- [ ] Native feed integration tests pass in CI.
- [ ] Operator training completed (native config, metrics, health checks).
- [ ] Tooling (`tools/backpack_auth_check.py`) distributed to support teams.

## GA Readiness
- [ ] Publish release notes announcing native feed availability and migration plan.
- [ ] Confirm downstream services support native-normalised symbols (`BTC-USDT`).
- [ ] Validate observability dashboards include Backpack metrics.
- [ ] Take snapshot of ccxt feed performance metrics for comparison.

## Rollout
- [ ] Enable `CRYPTOFEED_BACKPACK_NATIVE` in canary environment.
- [ ] Validate shadow mode parity (see runbook).
- [ ] Flip feature flag in production.
- [ ] Monitor for 24h and capture health snapshots.

## Post-GA Cleanup
- [ ] Remove `cryptofeed/exchanges/backpack_ccxt.py` and related tests.
- [ ] Delete ccxt-specific fixtures and docs.
- [ ] Update `docs/exchange.md` references to point to native feed.
- [ ] Close tracking issue linked to this checklist.
