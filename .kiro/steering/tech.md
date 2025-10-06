# Technology Stack

## Architecture
- **Language & Runtime:** Modern Python (3.11+ recommended; CI supports 3.8+)
  with asyncio as the concurrency backbone.
- **Event-Driven Feeds:** Each exchange transport runs asynchronously,
  preferring persistent WebSocket streams and using REST fallbacks for
  snapshots or exchanges without streaming support.
- **Transport Abstractions:** The refactored `cryptofeed/exchanges/ccxt/`
  package provides proxy-aware REST (`transport/rest.py`) and WebSocket
  (`transport/ws.py`) clients, normalised adapters, and a builder that reuses
  shared metadata caches.
- **Proxy System:** `cryptofeed/proxy.py` supplies global proxy settings,
  pool-aware selection strategies, and helpers consumed by all transports to
  enforce per-exchange overrides without code duplication.
- **Data Flow:** Exchange connectors normalise raw payloads into typed events
  that feed user callbacks or backends (Redis, Arctic, ZeroMQ, sockets). NBBO
  synthesis and optional backpressure handling sit on top of the feed layer.

## Core Dependencies
- **Networking:** `aiohttp`, `websockets`, `python-socks` (optional for SOCKS
  proxies), `aiohttp_socks` in legacy shims.
- **Exchange APIs:** `ccxt` and `ccxt.pro` deliver unified REST/WebSocket
  clients for long-tail venues.
- **Configuration & Validation:** `pydantic` v2 models and `pydantic-settings`
  secure typed configuration with environment interpolation.
- **Utilities:** `loguru` for structured logging, `ujson`/`simplejson` for fast
  serialization, `decimal` for precision handling, and `msgpack` for select
  backends.
- **Tooling:** `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`, and
  `black`/`isort`-aligned formatting conventions.

## Local Development
1. **Setup Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
2. **Run Tests**
   ```bash
   python -m pytest tests/ -v
   ```
3. **Type Checking**
   ```bash
   mypy cryptofeed/
   ```
4. **Lint & Format**
   ```bash
   ruff check cryptofeed/
   ruff format cryptofeed/
   ```

## Configuration & Environment
- **Global Settings:** `config.yaml` and environment variables feed the proxy
  system and exchange credentials. `ProxySettings` (pydantic) supports
  per-exchange HTTP/WebSocket URLs and pool strategies.
- **Exchange Config:** `cryptofeed/exchanges/ccxt/config.py` exposes typed
  models (`CcxtConfig`, `CcxtExchangeConfig`) that convert to runtime contexts
  with transport overrides, sandbox toggles, and auth credentials.
- **Credentials:** Secrets (API key, secret, passphrase) are loaded via config
  overrides or environment variables; never commit live credentials.
- **Examples:** `examples/` contains runnable scripts; some require specific
  env vars (e.g., `BACKPACK_API_KEY`) for authenticated channels.

## Observability & Operations
- **Logging:** Central `feedhandler` logger and `loguru` integration provide
  context-rich logs; transports add structured metadata (exchange, symbol,
  proxy endpoint) during retries.
- **Metrics (Roadmap):** Enhanced metrics collection is part of the CCXT spec
  follow-up, with placeholders in transports for counters.
- **Deployment:** Typical deployments run as long-lived Python services;
  containerised examples are available via the companion `Cryptostore` project.

## Common Commands Quick Reference
- `python -m pytest tests/unit/test_proxy_mvp.py -v`
- `python -m pytest tests/integration/test_proxy_integration.py -v`
- `python -m pytest tests/unit/test_ccxt_rest_transport.py -v`
- `python examples/backpack_live.py` (requires Backpack credentials & proxies)
- `cd docs && make html` to generate documentation locally.

