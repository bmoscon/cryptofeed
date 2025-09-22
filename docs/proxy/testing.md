# Proxy Testing Overview

## Test Inventory

| Suite | Scope | Key Assertions |
| --- | --- | --- |
| `tests/unit/test_proxy_mvp.py` | Configuration & logging utilities | Precedence, session reuse, sanitized logs |
| `tests/integration/test_proxy_http.py` | HTTP transports (native & CCXT) | Override vs default routing, direct mode behavior |
| `tests/integration/test_proxy_ws.py` | WebSocket transports | SOCKS/HTTP proxy parameters, ImportError, direct mode |

## Execution

```bash
pytest tests/unit/test_proxy_mvp.py tests/integration/test_proxy_http.py tests/integration/test_proxy_ws.py
```

## CI Matrix

- `python-socks=with`: validates SOCKS proxy flows.
- `python-socks=without`: ensures ImportError is raised when dependency missing.

## Logs & Metrics

- `feedhandler` logger outputs `proxy: transport=... scheme=... endpoint=...` with credentials stripped.
- Future enhancement: add metrics counters per exchange/scheme via fixtures.

