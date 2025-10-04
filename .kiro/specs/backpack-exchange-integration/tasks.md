# Implementation Plan

- [ ] 1. Enforce native-only activation for Backpack
- [x] 1.1 Lock FeedHandler routing to the native exchange modules
  - Resolve all Backpack registrations directly to the native feed implementation.
  - Guard runtime loaders so any attempt to reference the legacy identifier surfaces a migration error.
  - Ensure feature toggles default to the native path without requiring additional flags.
  - _Requirements: R1.1, R1.2, R1.3_

- [x] 1.2 Provide operator feedback for unsupported legacy configuration
  - Detect deprecated Backpack configuration keys during startup validation.
  - Emit actionable remediation guidance pointing to the native feed controls.
  - Block initialization whenever residual ccxt-era values are present.
  - _Requirements: R1.2, R2.3_

- [ ] 2. Strengthen configuration validation and credential handling
- [x] 2.1 Validate ED25519 credentials and sandbox selection rules
  - Normalize public and private key material regardless of input encoding.
  - Enforce window bounds, sandbox toggles, and deterministic endpoint resolution.
  - Surface precise validation errors when required values are missing or malformed.
  - _Requirements: R2.1, R2.2_

- [x] 2.2 Reject unsupported configuration fields with guided messaging
  - Inspect user-supplied settings for legacy or unknown attributes.
  - Provide migration hints explaining the streamlined configuration surface.
  - Prevent ambiguous fallbacks by failing fast on invalid keys.
  - _Requirements: R2.3_

- [ ] 3. Deliver proxy-integrated REST and WebSocket transports
- [x] 3.1 Route REST flows through the shared proxy subsystem
  - Resolve exchange-specific HTTP proxy overrides from the consolidated settings.
  - Execute snapshot and metadata requests using the pooled connection strategy.
  - Record transport metrics reflecting proxy rotations and retry attempts.
  - _Requirements: R3.1_

- [x] 3.2 Establish proxy-aware WebSocket sessions
  - Source WebSocket proxy information via the injector without bespoke logic.
  - Manage connection lifecycle with pooled proxy selection and rotation on failure.
  - Preserve subscription state across reconnects while emitting observability signals.
  - _Requirements: R3.2, R3.3_

- [ ] 4. Normalize Backpack market data for downstream consumers
- [ ] 4.1 Hydrate symbol metadata and maintain normalized mappings
  - Fetch market definitions and classify instrument types for spot and perpetual products.
  - Cache normalized-to-native symbol relationships for FeedHandler lookups.
  - Expose mapping utilities ensuring symmetry between normalized and exchange codes.
  - _Requirements: R4.1_

- [ ] 4.2 Translate trade and order book flows into standard data objects
  - Parse trade payloads with Decimal precision and attach exchange timestamps.
  - Reconcile order book snapshots and deltas while preserving sequence guarantees.
  - Emit normalized events through existing callback contracts.
  - _Requirements: R4.2_

- [ ] 4.3 Guard against malformed payloads with resilient handling
  - Detect schema mismatches or missing fields before dispatching events.
  - Log structured warnings identifying the offending channel and symbol.
  - Drop invalid messages without triggering fallback parsers.
  - _Requirements: R4.3_

- [ ] 5. Implement secure ED25519 authentication for private channels
- [ ] 5.1 Generate deterministic signatures and headers
  - Produce Base64-encoded ED25519 signatures using microsecond timestamps.
  - Package authentication headers with window constraints and optional passphrase handling.
  - Provide validation helpers highlighting incorrect key material or clock drift.
  - _Requirements: R5.1, R5.2_

- [ ] 5.2 Sustain private channel sessions with replay protection
  - Send authenticated WebSocket frames during session startup and resend after reconnects.
  - Rotate timestamps within the configured window while sessions remain active.
  - Surface explicit errors when verification fails and trigger controlled retries.
  - _Requirements: R5.2, R5.3_

- [ ] 6. Embed observability, testing, and operator guidance
- [ ] 6.1 Expand metrics and health reporting for Backpack
  - Track reconnects, authentication failures, parser issues, and proxy rotations.
  - Evaluate feed health based on snapshot freshness and stream cadence thresholds.
  - Expose snapshots suitable for dashboards and alerting workflows.
  - _Requirements: R6.1_

- [ ] 6.2 Build automated coverage across unit and integration flows
  - Create deterministic unit tests for configuration, auth signatures, symbol mapping, and routing.
  - Exercise integration paths covering proxy usage, snapshot/delta coherence, and private subscriptions.
  - Ensure suites run without mocks by leveraging fixtures and sandbox-safe payloads.
  - _Requirements: R6.1_

- [x] 6.3 Deliver operator-facing documentation and migration support
  - Document native setup steps, proxy expectations, and health verification procedures.
  - Publish migration guidance confirming retirement of the ccxt pathway.
  - Provide runnable examples showcasing public and private channel usage.
  - _Requirements: R6.2, R6.3_
