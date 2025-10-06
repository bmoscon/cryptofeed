# Implementation Tasks

## Milestone 1: Test Harness Foundations
- [x] Build parameterized proxy precedence fixtures (environment, YAML, programmatic) with teardown safety.
- [x] Add logging capture helpers validating sanitized proxy log output.
- [x] Extend CI tox/pytest config to run proxy matrix suites with and without python-socks installed.

## Milestone 2: HTTP Transport Coverage
- [x] Implement unit tests ensuring `HTTPAsyncConn` respects precedence, override vs default, and session reuse.
- [x] Create integration tests verifying HTTP clients under CCXT and native exchanges use expected proxy URLs.
- [x] Assert credential redaction in logs when proxies include auth components.

## Milestone 3: WebSocket Transport Coverage
- [x] Implement unit tests covering SOCKS and HTTP proxy branches for `WSAsyncConn`, including header injection.
- [x] Add tests verifying ImportError path when python-socks is absent.
- [x] Validate direct WebSocket connections remain unaffected when proxies disabled.

## Milestone 4: End-to-End Feed Scenarios
- [x] Add CCXT-focused coverage (backpack) verifying proxy defaults and overrides across HTTP/WS transports.
- [x] Add native feed coverage (binance) confirming overrides and direct-mode disable paths for REST and WebSocket clients.
- [x] Validate mixed global + per-exchange configurations yield expected routing matrix.

## Milestone 5: Documentation & Reporting
- [x] Document proxy test execution commands and matrix markers in `docs/proxy/user-guide.md` and CI docs.
- [x] Publish proxy test summary/coverage report in `docs/proxy/testing.md`.
- [x] Update CLAUDE.md Active Specifications status once implementation completes.
