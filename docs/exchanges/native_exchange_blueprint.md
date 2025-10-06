# Native Exchange Blueprint

## Overview
To keep native (non-CCXT) integrations aligned with the project’s engineering
principles, reuse the modular pattern established by the Backpack exchange.
This document captures reusable components and outlines how to share them
across future exchanges.

## Reusable Components Identified (Backpack)
- **Configuration (`config.py`)**: Pydantic models for exchange endpoints,
  authentication settings, feature toggles.
- **Authentication (`auth.py`)**: ED25519 signing helper with consistent header
  construction and error handling.
- **REST client (`rest.py`)**: Thin wrapper around `HTTPAsyncConn`, returning
  typed dataclasses for snapshots and metadata.
- **WebSocket session (`ws.py`)**: Connection lifecycle, heartbeat management,
  authentication refresh, and subscription payload handling.
- **Symbol service (`symbols.py`)**: Native symbol metadata, normalization, and
  cached market snapshots.
- **Metrics & Health (`metrics.py`, `health.py`)**: Collected counters and
  health-evaluation helpers decoupled from transport logic.
- **Feed integration (`feed.py`)**: Bridges native clients into the `Feed`
  hierarchy while respecting proxy injection and callback registration.

## Shared Toolkit Extraction Plan
1. **Auth Base (`native/auth.py`)**
   - Provide a reusable ED25519 signing helper with pluggable header names.
2. **REST Base (`native/rest.py`)**
   - Offer an async context manager wrapping `HTTPAsyncConn`, ready for
     exchange-specific endpoints and response adapters.
3. **WebSocket Base (`native/ws.py`)**
   - Manage connection/heartbeat lifecycle, subscription helpers, and optional
     metrics plumbing.
4. **Observability (`native/metrics.py`, `native/health.py`)**
   - Supply dataclasses or mixins for recording counters and reporting health
     status.

## Toolkit Modules (2025-10 Update)
- **`native/symbols.py`** – Provides `NativeSymbolService` and `NativeMarket`
  for TTL-aware symbol caching, normalization, and metadata fan-out. Subclasses
  override `_include_market`, `_normalize_symbol`, and `_build_market` to inject
  venue specifics without rewriting cache logic.
- **`native/router.py`** – Supplies `NativeMessageRouter`, a JSON-decoding
  dispatcher that records parser/dropped metrics, understands multiple channel
  fields, and delegates to registered handlers.
- **`native/auth.py` / `native/rest.py` / `native/ws.py`** – Continue to provide
  ED25519 auth helpers and proxy-aware transport primitives consumed by native
  exchanges.
- **`native/metrics.py` & `native/health.py`** – Offer lightweight counters and
  coarse health evaluation hooks; exchange-specific metrics types subclass the
  base container.

```python
from cryptofeed.exchanges.native import NativeMessageRouter, NativeSymbolService


class ExampleSymbolService(NativeSymbolService):
    def _include_market(self, entry):
        return entry.get("status") == "TRADING"

    def _normalize_symbol(self, native_symbol, entry):
        return native_symbol.replace('_', '-')


router = NativeMessageRouter(metrics=metrics)
router.register_handler("trades", handle_trade)
router.register_handler("orderbook", handle_orderbook)
```

Exchange implementations subclass these helpers to keep bespoke logic focused
on business rules while the toolkit handles caching, metrics, and drop logging.

Backpack modules would then subclass these base helpers, allowing other native
exchanges to reuse the same toolkit with minimal boilerplate.

## Next Steps
- **Phase 8.1** Identify and document reusable Backpack components *(complete
  in this document).* 
- **Phase 8.2** Extract the shared toolkit into `cryptofeed/exchanges/native/`
  and write unit coverage for the base helpers.
- **Phase 8.3** Refactor Backpack to subclass the shared toolkit and rerun the
  native + CCXT test suites.
- **Phase 8.4** Update developer documentation, linking this blueprint and
  showing how to scaffold new exchanges.

Keep this document updated as native exchanges adopt the shared tooling.
