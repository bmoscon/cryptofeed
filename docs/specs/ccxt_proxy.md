# ccxt/ccxt.pro Proxy & Endpoint Overrides

## Motivation

- Some exchanges (Binance, Backpack) block requests from certain regions (HTTP 451). Operators need a documented path to route traffic through compliant hosts or proxies.
- Provide consistent configuration knobs for both REST and WebSocket transports, aligning with the generic ccxt adapter.

## Configuration Fields

```yaml
proxies:
  rest: socks5://user:pass@host:1080    # or http://
  websocket: socks5://user:pass@host:1081
endpoints:
  rest: https://api.backpack.exchange
  websocket: wss://ws.backpack.exchange
retry:
  max_attempts: 3
  backoff_seconds: 1
```

- `proxies.rest` – forwarded to ccxt async client (`client.proxies`).
- `proxies.websocket` – forwarded to ccxt.pro (`exchange.options['ws_proxy']`).
- `endpoints` – overrides base URLs when ccxt metadata is missing or regional hosts are preferred.
- `retry` – simple retry parameters for transient proxy failures.

## Implementation Tasks

1. Extend `CcxtGenericFeed` (and transports) to accept proxy/endpoint parameters and apply them during client construction.
2. Add unit tests mocking ccxt clients to ensure proxies/endpoints propagate correctly.
3. Update documentation (README + exchange specs) once validated.

## Engineering Principles

- SOLID: Keep proxy handling within transport creation, not scattered across feed logic.
- KISS: Initial retry logic can be simple (fixed backoff); avoid complex strategies until needed.
- DRY: Generic implementation reused by Backpack and future ccxt-based feeds.
- YAGNI: Only support proxies for REST/WS; defer auth proxies or per-channel overrides until required.


## External Proxy Manager Integration

- Allow operators to supply a `proxy_resolver` callable (or plugin entry-point) that
  returns proxy settings at runtime. Example signature::

    def resolve_proxies(exchange_id: str) -> dict[str, str]:
        return {"rest": "socks5://...", "websocket": "http://..."}

- `CcxtGenericFeed` should call the resolver during initialization so dynamically
  rotated proxies (from a proxy management system or service mesh) are honoured.
- If resolver returns empty values, fall back to static configuration.
- Log the effective proxy target (without credentials) to aid observability.

## Non-ccxt Clients

- Reuse the proxy schema for other HTTP/WebSocket clients inside Cryptofeed
  (e.g., `requests`, `aiohttp`, native websocket connections) to provide a
  consistent operator experience.
- Implement a small helper (`apply_proxy_settings(session, proxies)`) that can be
  reused across exchanges/backends.
- Ensure proxy-aware unit tests exist for at least one native exchange connector
  once the helper is available.


## Extending proxies beyond ccxt

- Introduce a shared proxy configuration helper (e.g., `get_proxy_settings(feed_name)`)
  that native HTTP/WebSocket clients (requests, aiohttp, websocket-client) can call
  to obtain REST/WS proxy settings without code changes.
- Config schema should allow per-feed overrides and optionally reference external
  resolvers (same interface as ccxt).
- Update legacy connectors (e.g., native Binance/OKX) to consume the helper in a
  follow-up cycle, starting with documentation and unit tests.

