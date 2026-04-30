# Feature Spec Summary: Forge Production Image

**Feature ID**: FEAT-FORGE-009
**Stack**: python
**Generated**: 2026-04-30T00:00:00Z
**Scenarios**: 27 total (6 smoke, 4 regression)
**Assumptions**: 10 total (3 high / 4 medium / 3 low confidence)
**Review required**: Yes (3 low-confidence assumptions)

## Scope

Specifies the canonical production container image for forge — a multi-stage
Dockerfile based on a digest-pinned `python:3.14-slim-bookworm`, a new
`forge serve` long-lived daemon subcommand that subscribes to JetStream
`pipeline.build-queued.*`, and the CI / image-hygiene gates that protect the
LES1 parity properties (CMDW, PORT, ARFS, canonical-freeze) which Phase 6 of
`RUNBOOK-FEAT-FORGE-008-validation.md` is currently blocked on. The spec
covers the build path, the runtime contract (CLI surface, manifest
completeness, health probe, non-root user, no baked secrets), and the
operational edges (NATS reconnect, duplicate-delivery prevention, stale-image
detection, broker outage recovery, architecture-mismatch failure).

## Scenario Counts by Category

| Category | Count |
|----------|-------|
| Key examples (@key-example) | 5 |
| Boundary conditions (@boundary) | 5 |
| Negative cases (@negative) | 6 |
| Edge cases (@edge-case) | 12 |
| **Total scenarios** | **27** |
| Smoke set (@smoke) | 6 |
| Regression set (@regression) | 4 |

> Note: tag totals overlap — `@boundary @negative` and `@edge-case @regression`
> appear on the same scenarios. The 27-scenario total is the unique count.

## Specification by Example Group Breakdown

| Group | Theme | Scenario count |
|-------|-------|----------------|
| A | Key examples (build, CLI surface, CMDW round-trip, ARFS, canonical-freeze) | 5 |
| B | Boundaries (no-keys start, default NATS, install literal-match, size budget, health states) | 5 |
| C | Negatives (no baked keys, non-root, missing build context, no editable install, invalid config) | 5 |
| D | Edge cases — core (stale manifest, dual daemons, broker outage, cache poisoning, CI triggers) | 5 |
| E1 | Edge cases — security (digest pinning, volume escape, no remote-access endpoints) | 3 |
| E2 | Edge cases — data integrity (crash redelivery, artefact volume persistence) | 2 |
| E3 | Edge cases — integration (provider failure isolation, arch mismatch fast-fail) | 2 |

## Deferred Items

None. All proposed groups (A, B, C, D, E1, E2, E3) were accepted in full.

## Open Assumptions (low confidence — REVIEW REQUIRED)

These three assumptions need operator verification before implementation:

| ID | Topic | Proposed value |
|----|-------|----------------|
| ASSUM-003 | Image-size budget | 1.0 GB uncompressed |
| ASSUM-005 | Health probe / serve port | 8080 |
| ASSUM-007 | NATS reconnect window | Inherit JetStream durable consumer defaults |

ASSUM-005 is explicitly noted as an open question in scoping doc §11.2 —
expect feature-plan to settle it.

## Crosscut to Scoping AC Sketch

| Scoping AC (§10) | Covered by scenario(s) |
|---|---|
| AC-A — image builds from fresh clone | A1 |
| AC-B — `forge --help` shows full surface | A2 |
| AC-C — `forge serve` subscribes & receives payload | A3 |
| AC-D — manifest lists every fleet tool | A4 |
| AC-E — `pip install .[providers]` literal-match | A1 (last clause), B3 |
| AC-F — no real provider keys in any layer | C1 |
| AC-G — non-root runtime | C2 |
| AC-H — HEALTHCHECK declared & green | B5, E3.1 (boundary states) |
| AC-I — CI builds + smoke-tests on PR | D5 |
| AC-J — runbook §6 gating callout removed when feature merges | (governance, not behavioural — out of spec scope; tracked in feature-plan) |

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

    /feature-plan "FEAT-FORGE-009 Forge Production Image" \
      --context features/forge-production-image/forge-production-image_summary.md \
      --context docs/scoping/F8-007b-forge-production-dockerfile.md

The scoping doc remains the authoritative source for non-behavioural
context (image baseline rationale, multi-stage layout sketch, deferred CI
strategy, secrets-at-runtime guidance). This spec covers the *behavioural*
contract; feature-plan should layer task decomposition on top.
