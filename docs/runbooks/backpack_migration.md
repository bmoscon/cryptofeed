# Backpack Native Feed Migration Runbook

## Goals
- Transition production workloads from `CcxtBackpackFeed` to the native `BackpackFeed` implementation.
- Preserve downstream data fidelity (trades + L2) while activating ED25519 private channels.
- Capture telemetry that confirms healthy operation (snapshots fresh, no auth failures).

## Prerequisites
- Release including the native modules and `CRYPTOFEED_BACKPACK_NATIVE` feature flag.
- Operators aware of new configuration surface (ED25519 credentials, proxy overrides, metrics endpoints).
- Access to recorded fixtures for preflight validation (
  `tests/fixtures/backpack/`).

## Phases
1. **Dry Run (Sandbox)**
   - Enable feature flag in a staging or sandbox environment.
   - Run integration tests (`pytest tests/integration/test_backpack_native.py`).
   - Exercise `tools/backpack_auth_check.py` against staging credentials.

2. **Shadow Mode**
   - Enable native feed in read-only `FeedHandler` instance.
   - Compare metrics snapshots (`feed.metrics_snapshot()`) with ccxt path.
   - Monitor `feed.health().healthy` for at least 30 minutes.

3. **Primary Cutover**
   - Flip feature flag to `true` in production deployment.
   - Scale out FeedHandler instances gradually (10%, 50%, 100%).
   - Monitor:
     - `ws_errors`, `auth_failures`, `dropped_messages` (should remain zero).
     - Snapshot age (`symbol_snapshot_age`) < 30s.
     - Application-specific latency/error dashboards.

4. **Stabilisation**
   - Continue tracking metrics for 24 hours.
   - Capture post-cutover feedback from downstream consumers.
   - If anomalies detected, revert feature flag to `false` and re-queue investigation (see rollback).

## Rollback
- Toggle `CRYPTOFEED_BACKPACK_NATIVE=false` and redeploy.
- Restart FeedHandler processes to ensure `EXCHANGE_MAP` rebinds to ccxt feed.
- Document failure indicators (logs, metrics) in `docs/migrations/backpack_ccxt.md`.

## Success Criteria
- `BackpackFeed.health().healthy` remains `True` for 99% of checks.
- No increase in downstream error rate for Backpack pipelines.
- Private channel consumers receive authenticated updates with correct sequencing.

## Post-Migration Tasks
- Update operator runbooks to remove ccxt references.
- Remove redundant ccxt fixtures/tests after GA (tracked in `docs/migrations/backpack_ccxt.md`).
- Communicate completion to stakeholders.
