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

