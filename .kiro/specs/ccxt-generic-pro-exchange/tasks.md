# Task Breakdown (FR-first)

## Phase 1 – Functional Foundations
- [x] 1.1 Refine `CcxtConfig` and extension hooks
  - [x] 1.1.1 Audit existing fields and align validation with FR requirements
  - [x] 1.1.2 Update `CcxtConfigExtensions` decorator APIs and tests
  - [x] 1.1.3 Refresh config documentation with conventional commit guidance
  - _Requirements: R1.1, R1.2, R1.3_

- [x] 1.2 Restructure package layout for config/context modules
  - [x] 1.2.1 Create `config.py`, `context.py`, `extensions.py` under `cryptofeed/exchanges/ccxt/`
  - [x] 1.2.2 Add compatibility shims and update imports in functional modules/tests
  - [x] 1.2.3 Run smoke import tests to ensure FR surface unchanged
  - _Requirements: R5.1, R5.2, R5.3_

## Phase 2 – Transport Refactor (Functional Scope)
- [x] 2.1 Implement proxy-aware REST transport
  - [x] 2.1.1 Move REST helpers into `transport/rest.py` with ProxyInjector integration
  - [x] 2.1.2 Implement retry/backoff and minimal logging (advanced metrics deferred)
  - [x] 2.1.3 Update unit tests to cover proxy injection and error handling
  - _Requirements: R2.1, R2.2_

- [x] 2.2 Implement proxy-aware WebSocket transport
  - [x] 2.2.1 Create `transport/ws.py` with ProxyInjector integration and REST fallback
  - [x] 2.2.2 Provide basic connect/reconnect counters; mark advanced telemetry TODO
  - [x] 2.2.3 Add unit tests validating proxy usage and fallback behaviour
  - _Requirements: R2.2, R2.3_

## Phase 3 – Adapter & Registry Enhancements
- [x] 3.1 Define base adapters with normalization hooks
  - [x] 3.1.1 Extract base classes into modular package
  - [x] 3.1.2 Implement default symbol/timestamp/price normalization
  - [x] 3.1.3 Update concrete adapters to use new base classes
  - _Requirements: R3.1, R3.2, R3.3_

- [x] 3.2 Implement adapter registry with fallback behaviour
  - [x] 3.2.1 Build decorator-based registration API
  - [x] 3.2.2 Implement fallback resolution with structured logging tied to FR traceability
  - [x] 3.2.3 Refresh adapter registry tests (positive + negative cases)
  - _Requirements: R3.2_

## Phase 4 – Builder & Feed Integration
- [x] 4.1 Refactor `CcxtExchangeBuilder` and feed wrapper (functional scope)
  - [x] 4.1.1 Integrate new config/context/transport modules
  - [x] 4.1.2 Ensure REST-only fallback works when WebSocket disabled
  - [x] 4.1.3 Wire adapter registry into generated feed classes
  - _Requirements: R2.2, R4.1_

- [x] 4.2 Maintain compatibility shims (NO LEGACY)
  - [x] 4.2.1 Update legacy modules to re-export new package symbols
  - [x] 4.2.2 Run import smoke tests verifying functional compatibility
  - [x] 4.2.3 Document migration guidance, canonical imports, and removal timelines for shims
  - _Requirements: R5.2, R5.3_

## Phase 5 – Testing (Functional)
- [x] 5.1 Refresh unit test coverage ✅
  - [x] 5.1.1 Update config/transport/adapter unit tests to new modules
  - [x] 5.1.2 Add hooks/registry coverage; tag future NFR tests with `@pytest.mark.ccxt_future`
  - [x] 5.1.3 Remove legacy RED tests or update expectations to new behaviour
  - _Requirements: R4.1_

- [x] 5.2 Update integration fixtures ✅
  - [x] 5.2.1 Patch CCXT async/pro clients to validate proxy routing and auth hooks
  - [x] 5.2.2 Cover REST-only and REST+WS flows using recorded fixtures
  - [x] 5.2.3 Document fixture usage and FR-first sequencing
  - _Requirements: R4.2_

- [x] 5.3 Plan smoke tests for sandbox credentials (defer execution)
  - [x] 5.3.1 Define placeholder tests pending sandbox access
  - [x] 5.3.2 Capture credentials/logging TODOs for future spec
  - [x] 5.3.3 Note follow-up backlog item for NFR hardening
  - _Requirements: R4.2_

## Phase 6 – Documentation & Follow-up
- [x] 6.1 Update developer guide (`docs/exchanges/ccxt_generic.md`)
  - [x] 6.1.1 Describe new package structure and FR-first approach
  - [x] 6.1.2 Provide hook examples and conventional commit guidance
  - [x] 6.1.3 Add migration checklist, canonical import surface, and NO LEGACY reminders
  - _Requirements: R4.3_

- [x] 6.2 Update API reference & change notes
  - [x] 6.2.1 Document new public interfaces, re-export strategy, and shim removal plan
  - [x] 6.2.2 Add entry to `CHANGES.md` referencing this spec and migration impact
  - [x] 6.2.3 Include FAQ/troubleshooting for refactor adoption
  - _Requirements: R4.3, R5.3_

- [x] 6.3 Capture follow-up NFR backlog
  - [x] 6.3.1 Summarize remaining NFR work (metrics, performance)
  - [x] 6.3.2 Propose follow-on spec if needed
  - [x] 6.3.3 Update roadmap with FR completion milestone and shim removal timelines
  - _Requirements: R4.3_

## Phase 7 – Shim Retirement (NO LEGACY)
- [x] 7.1 Audit compatibility modules (`cryptofeed/exchanges/ccxt_*`) still required by downstream code
  - _Requirements: R5.3_
- [x] 7.2 Remove redundant shims (`ccxt_feed.py`, `ccxt_config.py`, `ccxt_transport.py`, `ccxt_adapters.py`) once consumers migrate
  - _Requirements: R5.3_
- [x] 7.3 Update documentation/changelog to record shim removal and provide migration reminders
  - _Requirements: R5.3_
- [x] 7.4 Monitor downstream adoption and remove temporary shims introduced for other exchanges as they migrate (ongoing)
  - _Requirements: R5.3_

## Phase 8 – Native Exchange Blueprint (Backpack extraction)
- [x] 8.1 Identify reusable components in `cryptofeed/exchanges/backpack/` (auth helper, REST/WS session mixins, metrics/health)
  - _Requirements: R3.1, R3.3_ — see `docs/exchanges/native_exchange_blueprint.md`
- [x] 8.2 Extract shared base helpers into a reusable native-exchange toolkit
  - _Requirements: R3.1, R3.2_
- [x] 8.3 Update Backpack to consume the shared toolkit (ensure tests pass)
  - _Requirements: R4.1_
- [x] 8.4 Document the blueprint for new native exchanges (developer guide section)
  - _Requirements: R4.3_
